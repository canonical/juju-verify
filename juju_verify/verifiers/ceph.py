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
from collections import defaultdict
from typing import Dict, Optional, Any, List

from juju.unit import Unit
from packaging.version import Version, InvalidVersion

from juju_verify.utils.action import data_from_action
from juju_verify.utils.unit import (
    verify_charm_unit,
    run_action_on_units,
    get_first_active_unit,
    get_applications_names
)
from juju_verify.verifiers.base import BaseVerifier
from juju_verify.verifiers.result import aggregate_results, Result, Severity
from juju_verify.exceptions import CharmException

logger = logging.getLogger()


class AvailabilityZone:
    """Availability zone."""

    def __init__(self, **data: str):
        """Availability zone initialization."""
        self._data = data

    def __getattr__(self, item: str) -> Optional[str]:
        """Get element from crush map hierarchy."""
        if item not in self.crush_map_hierarchy:
            raise AttributeError(f"'{self.__class__}' object has no attribute '{item}'")

        return self._data.get(item, None)

    def __eq__(self, other: object) -> bool:
        """Compare two Result instances."""
        if not isinstance(other, AvailabilityZone):
            return NotImplemented

        return str(self) == str(other)

    def __str__(self) -> str:
        """Return string representation of AZ objects."""
        return ",".join(
            [f"{crush_map_type}={self._data[crush_map_type]}" for crush_map_type
             in self.crush_map_hierarchy if crush_map_type in self._data]
        )

    def __hash__(self) -> int:
        """Return hash representation of AZ objects."""
        return hash(self.__str__())

    @property
    def crush_map_hierarchy(self) -> List[str]:
        """Get Ceph Crush Map hierarchy."""
        return [
            "root",  # 10
            "region",  # 9
            "datacenter",  # 8
            "room",  # 7
            "pod",  # 6
            "pdu",  # 5
            "row",  # 4
            "rack",  # 3
            "chassis",  # 2
            "host",  # 1
            "osd",  # 0
        ]


class CephCommon(BaseVerifier):  # pylint: disable=W0223
    """Parent class for CephMon and CephOsd verifier."""

    @classmethod
    def check_cluster_health(cls, *units: Unit) -> Result:
        """Check Ceph cluster health for specific units.

        This will execute `get-health` against each unit provided.

        :raises CharmException: if the units do not belong to the ceph-mon charm
        """
        verify_charm_unit("ceph-mon", *units)
        result = Result()
        action_map = run_action_on_units(list(units), "get-health")

        for unit, action in action_map.items():
            cluster_health = data_from_action(action, "message")
            logger.debug("Unit (%s): Ceph cluster health '%s'", unit, cluster_health)

            if "HEALTH_OK" in cluster_health and result.success:
                result.add_partial_result(Severity.OK,
                                          f"{unit}: Ceph cluster is healthy")
            elif "HEALTH_WARN" in cluster_health or "HEALTH_ERR" in cluster_health:
                result.add_partial_result(Severity.FAIL,
                                          f"{unit}: Ceph cluster is unhealthy")
            else:
                result.add_partial_result(Severity.FAIL,
                                          f"{unit}: Ceph cluster is in an unknown "
                                          f"state")

        if not action_map:
            result = Result(Severity.FAIL, "Ceph cluster is in an unknown state")

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
        action_map = run_action_on_units([unit], "list-pools", params={"format": "json"})
        action_output = data_from_action(action_map.get(unit.entity_id), "message", "[]")
        logger.debug("parse information about pools: %s", action_output)
        pools: List[Dict[str, Any]] = json.loads(action_output)

        if pools:
            return min(pool["size"] - pool["min_size"] for pool in pools)

        return None

    @classmethod
    def get_number_of_free_units(cls, unit: Unit) -> int:
        """Get number of free units from ceph df.

        The `ceph df` will provide a cluster’s data usage and data distribution among
        pools and this function calculates the number of units that are safe to remove.
        """
        verify_charm_unit("ceph-mon", unit)
        # NOTE (rgildein): This functionality is not complete and will be part of the
        #                  fix on LP#1921121.
        logger.warning("WARNING: The function to get the number of free units from "
                       "'ceph df' is in WIP and returns only 1. See LP#1921121 "
                       "for more information.")
        return 1

    @classmethod
    def get_availability_zones(cls,  *units: Unit) -> Dict[str, AvailabilityZone]:
        """Get information about availability zones for ceph-osd units."""
        # NOTE (rgildein): This has been tested, but it will be fully functional only
        #                  after merging the changes.
        #                  https://review.opendev.org/c/openstack/charm-ceph-osd/+/778159
        verify_charm_unit("ceph-osd", *units)
        action_map = run_action_on_units(list(units), "get-availability-zone")

        availability_zone = {}
        for unit, action in action_map.items():
            action_output = data_from_action(action, "availability-zone", "{}")
            unit_availability_zone = json.loads(action_output)["unit"]
            unit_availability_zone.pop("host")  # need to compare AZ without host
            availability_zone[unit] = AvailabilityZone(**unit_availability_zone)

        return availability_zone


class CephOsd(CephCommon):
    """Implementation of verification checks for the ceph-osd charm."""

    NAME = "ceph-osd"

    def __init__(self, units: List[Unit]):
        """Ceph-osd charm verifier."""
        super().__init__(units=units)
        self._ceph_mon_app_map: Optional[Dict[str, Unit]] = None

    @property
    def ceph_mon_app_map(self) -> Dict[str, Unit]:
        """Get a map between ceph-osd applications and the first ceph-mon unit.

        :returns: Dictionary with keys as distinct applications of verified units and
                  values as the first ceph-mon unit obtained from the relation with the
                  ceph-mon application (<application_name>:mon).
        """
        if self._ceph_mon_app_map is None:
            self._ceph_mon_app_map = self._get_ceph_mon_app_map()

        return self._ceph_mon_app_map

    def _get_ceph_mon_unit(self, app_name: str) -> Optional[Unit]:
        """Get first ceph-mon unit from relation."""
        try:
            for relation in self.model.applications[app_name].relations:
                if relation.matches(f"{app_name}:mon"):
                    return get_first_active_unit(relation.provides.application.units)

        except (IndexError, KeyError) as error:
            logger.debug("Error to get ceph-mon unit from relations: %s", error)

        return None

    def _get_ceph_mon_app_map(self) -> Dict[str, Unit]:
        """Get first ceph-mon units related to verified units.

        This function groups by distinct application names for verified units, and then
        finds the relation ("<application>:mon") between the application and ceph-mon.
        The first unit of ceph-mon will be obtained from this relation.
        :returns: Map between verified and ceph-mon units
        """
        applications = {unit.application for unit in self.units}
        logger.debug("affected applications %s", map(str, applications))

        app_map = {name: self._get_ceph_mon_unit(name) for name in applications}
        logger.debug("found units %s", map(str, app_map.values()))

        return {name: unit for name, unit in app_map.items() if unit is not None}

    def get_free_app_units(self, apps: List[str]) -> Dict[str, int]:
        """Get number of free units for each application."""
        free_units = {}
        for app_name in apps:
            ceph_mon_unit = self._get_ceph_mon_unit(app_name)
            if ceph_mon_unit:
                free_units[app_name] = self.get_number_of_free_units(ceph_mon_unit)

        return free_units

    def get_apps_availability_zones(
            self, apps: List[str]) -> Dict[AvailabilityZone, List[Unit]]:
        """Get information about availability zone for each ceph-osd unit in application.

        This function return dictionary contain AZ as key and list of units as value.
        e.g. {AZ(per_host=False, rack="nova", row=None): [<Unit entity_id="ceph-osd/0">]}
        """
        availability_zones = defaultdict(list)
        for app_name in apps:
            app_units = self.model.applications[app_name].units
            app_availability_zones = self.get_availability_zones(*app_units)
            for unit_id, availability_zone in app_availability_zones.items():
                availability_zones[availability_zone].append(self.model.units[unit_id])

        return availability_zones

    def check_ceph_cluster_health(self) -> Result:
        """Check Ceph cluster health for unique ceph-mon units from ceph_mon_app_map."""
        unique_ceph_mon_units = set(self.ceph_mon_app_map.values())
        return self.check_cluster_health(*unique_ceph_mon_units)

    def check_replication_number(self) -> Result:
        """Check the minimum number of replications for related applications."""
        result = Result()

        for app_name, ceph_mon_unit in self.ceph_mon_app_map.items():
            min_replication_number = self.get_replication_number(ceph_mon_unit)
            if min_replication_number is None:
                continue  # get_replication_number returns None if no pools are available

            units = {
                unit.entity_id for unit in self.units if unit.application == app_name
            }
            inactive_units = {
                unit.entity_id for unit in self.model.applications[app_name].units
                if unit.workload_status != "active"
            }

            if len(units.union(inactive_units)) > min_replication_number:
                result.add_partial_result(
                    Severity.FAIL,
                    f"The minimum number of replicas in '{app_name}' is "
                    f"{min_replication_number:d} and it's not safe to restart/shutdown "
                    f"{len(units):d} units. {len(inactive_units):d} units are not "
                    f"active."
                )

        if result.empty:
            result.add_partial_result(Severity.OK,
                                      'Minimum replica number check passed.')
        return result

    def check_availability_zone(self) -> Result:
        """Check availability zones resources.

        This function checks whether the units can be shutdown/reboot without
        interrupting operation in the availability zone.
        """
        result = Result()
        ceph_osd_apps = get_applications_names(self.model, "ceph-osd")
        free_app_units = self.get_free_app_units(ceph_osd_apps)
        availability_zones = self.get_apps_availability_zones(ceph_osd_apps)

        for availability_zone, units in availability_zones.items():
            inactive_units = {
                unit.entity_id for unit in units if unit.workload_status != "active"
            }
            units_to_remove = {
                unit.entity_id for unit in units if unit.entity_id in self.unit_ids
            }
            free_units = min(free_app_units[unit.application] for unit in units)
            logger.debug("The availability zone %s has %d inactive and %d free units. "
                         "Trying to remove %s units.", str(availability_zone),
                         len(inactive_units), free_units, units_to_remove)

            if len(units_to_remove.union(inactive_units)) > free_units:
                result += Result(
                    Severity.FAIL,
                    f"It's not safe to removed units {units_to_remove} in the "
                    f"availability zone '{availability_zone}'. [free_units="
                    f"{free_units:d}, inactive_units={len(inactive_units):d}]"
                )

        if result.empty:
            result.add_partial_result(Severity.OK,
                                      'Availability zone check passed.')
        return result

    def verify_reboot(self) -> Result:
        """Verify that it's safe to reboot selected ceph-osd units."""
        return aggregate_results(self.check_ceph_cluster_health(),
                                 self.check_replication_number(),
                                 self.check_availability_zone())

    def verify_shutdown(self) -> Result:
        """Verify that it's safe to shutdown selected ceph-osd units."""
        return self.verify_reboot()


class CephMon(CephCommon):
    """Implementation of verification checks for the ceph-mon charm."""

    NAME = "ceph-mon"

    def verify_reboot(self) -> Result:
        """Verify that it's safe to reboot selected ceph-mon units."""
        version_check = self.check_version()
        if not version_check.success:
            return version_check

        # Get one ceph-mon unit per each application
        app_map = {unit.application: unit for unit in self.units}
        unique_app_units = app_map.values()

        return aggregate_results(
            version_check,
            self.check_quorum(),
            self.check_cluster_health(*unique_app_units)
        )

    def verify_shutdown(self) -> Result:
        """Verify that it's safe to shutdown selected units."""
        return self.verify_reboot()

    def check_quorum(self) -> Result:
        """Check that the shutdown does not result in <50% mons alive."""
        result = Result()

        action_name = "get-quorum-status"
        action_results = self.run_action_on_all(action_name)

        affected_hosts = {unit.machine.hostname for unit in self.units}

        for unit_id, action in action_results.items():
            # run this per unit because we might have multiple clusters
            known_mons = set(json.loads(data_from_action(action, "known-mons")))
            online_mons = set(json.loads(data_from_action(action, "online-mons")))

            mon_count = len(known_mons)
            mons_after_change = len(online_mons - affected_hosts)

            if mons_after_change <= mon_count // 2:
                result.add_partial_result(Severity.FAIL, f"Removing unit {unit_id} will"
                                                         f" lose Ceph mon quorum")

        if result.empty:
            result.add_partial_result(Severity.OK, 'Ceph-mon quorum check passed.')

        return result

    def check_version(self) -> Result:
        """Check minimum required version of juju agents on units.

        Ceph-mon verifier requires that all the units run juju agent >=2.8.10 due to
        reliance on juju.Machine.hostname feature.
        """
        min_version = Version('2.8.10')
        result = Result()
        for unit in self.units:
            juju_version = unit.safe_data.get('agent-status', {}).get('version', '')
            try:
                if Version(juju_version) < min_version:
                    fail_msg = (f'Juju agent on unit {unit.entity_id} has lower than '
                                f'minumum required version. {juju_version} < '
                                f'{min_version}')
                    result.add_partial_result(Severity.FAIL, fail_msg)
            except InvalidVersion as exc:
                raise CharmException(f'Failed to parse juju version from '
                                     f'unit {unit.entity_id}.') from exc

        if result.empty:
            result.add_partial_result(Severity.OK, 'Minimum juju version check passed.')

        return result
