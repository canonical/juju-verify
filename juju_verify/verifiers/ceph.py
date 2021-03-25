# Copyright 2021 Canonical Limited.
#
# This file is part of juju-verify.
#
# juju-verify is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# juju-verify is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program. If not, see https://www.gnu.org/licenses/.
"""ceph-osd verification."""

import json
import logging
from typing import Dict, Optional

from juju.unit import Unit

from juju_verify.utils.action import data_from_action
from juju_verify.utils.unit import run_action_on_units, verify_charm_unit
from juju_verify.verifiers.base import BaseVerifier
from juju_verify.verifiers.result import Result, aggregate_results

logger = logging.getLogger()


class CephCommon(BaseVerifier):  # pylint: disable=W0223
    """Parent class for CephMon and CephOsd verifier."""

    @classmethod
    def check_cluster_health(cls, *units: Unit) -> Result:
        """Check Ceph cluster health for specific units.

        This will execute `get-health` against each unit provided.
        """
        verify_charm_unit("ceph-mon", *units)
        result = Result(success=True)
        action_map = run_action_on_units(list(units), "get-health")

        for unit, action in action_map.items():
            cluster_health = data_from_action(action, "message")
            logger.debug("Unit (%s): Ceph cluster health '%s'", unit, cluster_health)

            if "HEALTH_OK" in cluster_health and result.success:
                result += Result(True, f"{unit}: Ceph cluster is healthy")
            elif "HEALTH_WARN" in cluster_health or "HEALTH_ERR" in cluster_health:
                result += Result(False, f"{unit}: Ceph cluster is unhealthy")
            else:
                result += Result(False, f"{unit}: Ceph cluster is in an unknown state")

        if not action_map:
            result = Result(success=False, reason="Ceph cluster is in an unknown state")

        return result


class CephOsd(CephCommon):
    """Implementation of verification checks for the ceph-osd charm."""

    NAME = "ceph-osd"

    def _get_ceph_mon_unit(self, app_name: str) -> Optional[Unit]:
        """Get first ceph-mon unit from relation."""
        try:
            for relation in self.model.applications[app_name].relations:
                if relation.matches(f"{app_name}:mon"):
                    # selecting the first unit from the application provided by relation
                    return relation.provides.application.units[0]
        except (IndexError, KeyError) as error:
            logger.debug("Error to get ceph-mon unit from relations: %s", error)

        return None

    def get_ceph_mon_units(self) -> Dict[str, Unit]:
        """Get first ceph-mon units related to verified units.

        This function groups by distinct application names for verified units, and then
        finds the relation ("<application>:mon") between the application and ceph-mon.
        The first unit of ceph-mon will be obtained from this relation.
        :returns: Map between verified and ceph-mon units
        """
        applications = {unit.application for unit in self.units}
        logger.debug("affected applications %s", map(str, applications))

        ceph_mon_app_map = {}
        for app_name in applications:
            unit = self._get_ceph_mon_unit(app_name)
            if unit is not None:
                ceph_mon_app_map[app_name] = unit

        logger.debug("found units %s", map(str, ceph_mon_app_map.values()))

        return ceph_mon_app_map

    def verify_reboot(self) -> Result:
        """Verify that it's safe to reboot selected ceph-osd units."""
        ceph_mon_app_map = self.get_ceph_mon_units()
        # get unique ceph-mon units
        unique_ceph_mon_units = set(ceph_mon_app_map.values())
        return aggregate_results(self.check_cluster_health(*unique_ceph_mon_units))

    def verify_shutdown(self) -> Result:
        """Verify that it's safe to shutdown selected ceph-osd units."""
        return self.verify_reboot()


class CephMon(CephCommon):
    """Implementation of verification checks for the ceph-mon charm."""

    NAME = "ceph-mon"

    def verify_reboot(self) -> Result:
        """Verify that it's safe to reboot selected ceph-mon units."""
        return aggregate_results(
            self.check_quorum(), self.check_cluster_health(*self.units)
        )

    def verify_shutdown(self) -> Result:
        """Verify that it's safe to shutdown selected units."""
        return self.verify_reboot()

    def check_quorum(self) -> Result:
        """Check that the shutdown does not result in <50% mons alive."""
        result = Result(success=True)

        action_name = "get-quorum-status"
        action_results = self.run_action_on_all(action_name)

        mons = {}
        affected_hosts = set()

        for unit in self.units:
            # set of affected hostnames needs to be fully populated early
            # from online mons

            if unit.machine.hostname:
                affected_hosts.update(
                    [unit.machine.hostname]
                )
            else:
                # we don't have a hostname for this unit
                logger.error(
                    "The machine for unit %s did not return a hostname", unit.entity_id
                )
                result.success = False
                result.reason += (
                    "The machine for unit {} does not have a hostname attribute, please"
                    "ensure that Juju is 2.8.10+\n".format(unit.entity_id)
                )

        # populate a list of known mons, online mons and hostnames per unit
        for unit_id, action in action_results.items():
            # run this per unit because we might have multiple clusters
            mons[unit_id] = {
                "known": set(json.loads(data_from_action(action, "known-mons"))),
                "online": set(json.loads(data_from_action(action, "online-mons"))),
            }

        for unit in self.units:
            mon_count = len(mons[unit.entity_id]["known"])
            mons_after_change = len(mons[unit.entity_id]["online"] - affected_hosts)

            if mons_after_change <= mon_count / 2:
                result.success = False
                result.reason += (
                    "Removing unit {} will lose Ceph mon "
                    "quorum\n".format(unit.entity_id)
                )

        return result
