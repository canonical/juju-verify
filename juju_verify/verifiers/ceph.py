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
from typing import Dict, Optional, Any, List

from juju.unit import Unit

from juju_verify.utils.action import data_from_action
from juju_verify.utils.unit import verify_charm_unit, run_action_on_units
from juju_verify.verifiers.base import BaseVerifier
from juju_verify.verifiers.result import aggregate_results, Result

logger = logging.getLogger()


class CephCommon(BaseVerifier):  # pylint: disable=W0223
    """Parent class for CephMon and CephOsd verifier."""

    @classmethod
    def check_cluster_health(cls, *units: Unit) -> Result:
        """Check Ceph cluster health for specific units.

        This will execute `get-health` against each unit provided.

        :raises CharmException: if the units do not belong to the ceph-mon charm
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

    @classmethod
    def get_replication_number(cls, unit: Unit) -> Optional[int]:
        """Get minimum replication number from ceph-mon unit.

        This function runs the `list-pools` action with the parameter 'detail=true'
        to get the replication number.
        :raises CharmException: if the unit does not belong to the ceph-mon charm
        :raises TypeError: if the object pools is not iterable
        :raises KeyError: if the pool detail does not contain `size` or `min_size`
        :raises json.decoder.JSONDecodeError: if json.loads failed
        """
        verify_charm_unit("ceph-mon", unit)
        action_map = run_action_on_units([unit], "list-pools", detail=True)
        action_output = data_from_action(action_map.get(unit.entity_id), "pools")
        logger.debug("parse information about pools: %s", action_output)
        pools: List[Dict[str, Any]] = json.loads(action_output)

        if pools:
            return min([pool["size"] - pool["min_size"] for pool in pools])

        return None


class CephOsd(CephCommon):
    """Implementation of verification checks for the ceph-osd charm."""

    NAME = 'ceph-osd'

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

    def check_replication_number(self, ceph_mon_app_map: Dict[str, Unit]) -> Result:
        """Check the minimum number of replications for related applications."""
        result = Result(True)

        for app_name, ceph_mon_unit in ceph_mon_app_map.items():
            min_replication_number = self.get_replication_number(ceph_mon_unit)
            number_of_units = len([unit for unit in self.units
                                   if unit.application == app_name])

            if min_replication_number and number_of_units > min_replication_number:
                result += Result(False,
                                 f"The minimum number of replications in '{app_name}' "
                                 f"is {min_replication_number:d} and it's not safe to "
                                 f"restart/shutdown {number_of_units:d} units.")

        return result

    def verify_reboot(self) -> Result:
        """Verify that it's safe to reboot selected ceph-osd units."""
        ceph_mon_app_map = self.get_ceph_mon_units()
        # get unique ceph-mon units
        unique_ceph_mon_units = set(ceph_mon_app_map.values())
        return aggregate_results(self.check_cluster_health(*unique_ceph_mon_units),
                                 self.check_replication_number(ceph_mon_app_map))

    def verify_shutdown(self) -> Result:
        """Verify that it's safe to shutdown selected ceph-osd units."""
        return self.verify_reboot()
