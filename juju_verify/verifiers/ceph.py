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
from typing import Any, Dict, List, NamedTuple, Optional, Set, Tuple

from juju.action import Action
from juju.unit import Unit
from packaging.version import Version

from juju_verify.utils.action import data_from_action
from juju_verify.utils.unit import (
    get_first_active_unit,
    run_action_on_units,
    verify_charm_unit,
)
from juju_verify.verifiers.base import BaseVerifier
from juju_verify.verifiers.result import Result, Severity, checks_executor

logger = logging.getLogger()


class NodeInfo(NamedTuple):
    """Information about Node obtains from `ceph df osd tree`.

    The `ceph df` [1] comes from ceph-mon unit and it's run with additional option
    `tree` to show output in Crush Map hierarchy format.
    The Crush Map hierarchy [2] contains the following types along with their IDs.

    List of types and their id:
    root: 10
    region: 9
    datacenter: 8
    room: 7
    pod: 6
    pdu: 5
    row: 4
    rack: 3
    chassis: 2
    host: 1
    osd: 0

    [1]: https://docs.ceph.com/en/latest/api/mon_command_api/#df
    [2]: https://docs.ceph.com/en/latest/rados/operations/crush-map/#types-and-buckets
    """

    id: int
    name: str
    type_id: int
    type: str
    kb: int
    kb_used: int
    kb_avail: int
    children: Optional[List[int]] = None

    def __str__(self) -> str:
        """Return string representation of Node."""
        return f"{self.name}({self.id})"

    def __hash__(self) -> int:
        """Return hash representation of Node."""
        return hash(self.__str__())


class AvailabilityZone:
    """Availability zone."""

    def __init__(self, nodes: List[NodeInfo]):
        """Availability zone initialization.

        The nodes argument come from the output of the `ceph df osd tree` command,
        while the type `host` has the name corresponding to the hostname of the machine.
        """
        self._nodes = nodes

    def __eq__(self, other: object) -> bool:
        """Compare two Result instances."""
        if not isinstance(other, AvailabilityZone):
            return NotImplemented

        return self._nodes == other._nodes

    def __str__(self) -> str:
        """Return string representation of AZ objects."""
        return ",".join(
            str(node)
            for node in sorted(self._nodes, key=lambda node: node.type_id, reverse=True)
        )

    def __hash__(self) -> int:
        """Return hash representation of AZ objects."""
        return hash(self.__str__())

    def find_parent(self, node_id: int) -> Optional[NodeInfo]:
        """Find the node that has the id in the children list."""
        for node in self._nodes:
            if node.children and node_id in node.children:
                return node

        return None

    def get_nodes(self, name: str) -> List[NodeInfo]:
        """Get nodes by their name."""
        nodes = [node for node in self._nodes if node.name == name]
        if not nodes:
            raise KeyError(f"Node {name} was not found.")

        return nodes

    def can_be_removed(self, *names: str) -> bool:
        """Check if child could be removed."""
        # Finds matching parents for children.
        parents_children_map = defaultdict(list)
        for name in names:
            # NOTE (rgildein): `Self.get_node` could raise an error here, but the
            #                  check runner catches all exceptions.
            children = self.get_nodes(name)
            for child in children:
                parent = self.find_parent(child.id)
                if not parent:
                    logger.warning(
                        "A parent for the node %s could not be found.", child
                    )
                    return False

                parents_children_map[parent].append(child)

        # Check if all children could be removed from parent.
        for parent, children in parents_children_map.items():
            # NOTE (rgildein): This will check that the parent will have enough space
            #                  even if the children are removed.
            #                  example with attempt to remove 3 children:
            #                    parent has 1 000 KB (1MB) free space
            #                    space that children use is 200 KB each (600 KB total)
            #                    data from deleted children will fit on the parent
            if parent.kb_avail <= sum(child.kb_used for child in children):
                logger.debug(
                    "Lack of space. Children %s cannot be removed.",
                    ",".join(str(child) for child in children),
                )
                return False

        return True


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
                result.add_partial_result(
                    Severity.OK, f"{unit}: Ceph cluster is healthy"
                )
            elif "HEALTH_WARN" in cluster_health or "HEALTH_ERR" in cluster_health:
                result.add_partial_result(
                    Severity.FAIL, f"{unit}: Ceph cluster is unhealthy"
                )
            else:
                result.add_partial_result(
                    Severity.FAIL, f"{unit}: Ceph cluster is in an unknown state"
                )

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
        action_map = run_action_on_units(
            [unit], "list-pools", params={"format": "json"}
        )
        action_output = data_from_action(
            action_map.get(unit.entity_id), "message", "[]"
        )
        logger.debug("parse information about pools: %s", action_output)
        pools: List[Dict[str, Any]] = json.loads(action_output)

        if pools:
            return min(pool["size"] - pool["min_size"] for pool in pools)

        return None

    @classmethod
    def get_disk_utilization(cls, unit: Unit) -> List[NodeInfo]:
        """Get disk utilization as osd tree output."""
        verify_charm_unit("ceph-mon", unit)
        # NOTE (rgildein): The `show-disk-free` action will provide output w/ 3 keys,
        #                  while this function uses only one, namely `nodes`.
        #                  https://github.com/openstack/charm-ceph-mon#actions
        action_map = run_action_on_units(
            [unit], "show-disk-free", params={"format": "json"}
        )
        action_output = data_from_action(
            action_map.get(unit.entity_id), "message", "{}"
        )
        logger.debug("parse information about disk utilization: %s", action_output)
        osd_tree: Dict[str, Any] = json.loads(action_output)
        return [
            NodeInfo(
                id=node["id"],
                name=node["name"],
                type=node["type"],
                type_id=node["type_id"],
                kb=node["kb"],
                kb_used=node["kb_used"],
                kb_avail=node["kb_avail"],
                children=node.get("children"),
            )
            for node in osd_tree["nodes"]
        ]


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
                unit.entity_id
                for unit in self.model.applications[app_name].units
                if unit.workload_status != "active"
            }

            if len(units.union(inactive_units)) > min_replication_number:
                result.add_partial_result(
                    Severity.FAIL,
                    f"The minimum number of replicas in '{app_name}' is "
                    f"{min_replication_number:d} and it's not safe to restart/shutdown "
                    f"{len(units):d} units. {len(inactive_units):d} units are not "
                    f"active.",
                )

        return result or Result(Severity.OK, "Minimum replica number check passed.")

    def check_availability_zone(self) -> Result:
        """Check availability zones resources.

        This function checks whether the units can be shutdown/reboot without
        interrupting operation in the availability zone.
        """
        result = Result()
        for ceph_osd_app, ceph_mon_unit in self.ceph_mon_app_map.items():
            availability_zone = AvailabilityZone(
                nodes=self.get_disk_utilization(ceph_mon_unit)
            )
            units = [unit for unit in self.units if unit.application == ceph_osd_app]
            affected_hosts = {unit.machine.hostname for unit in units}

            if not availability_zone.can_be_removed(*affected_hosts):
                units_to_remove = ", ".join(unit.entity_id for unit in units)
                result += Result(
                    Severity.FAIL,
                    f"It's not safe to removed units {units_to_remove} in the "
                    f"availability zone '{availability_zone}'.",
                )

        return result or Result(Severity.OK, "Availability zone check passed.")

    def verify_reboot(self) -> Result:
        """Verify that it's safe to reboot selected ceph-osd units."""
        return checks_executor(
            self.check_ceph_cluster_health,
            self.check_replication_number,
            self.check_availability_zone,
        )

    def verify_shutdown(self) -> Result:
        """Verify that it's safe to shutdown selected ceph-osd units."""
        return self.verify_reboot()


class CephMon(CephCommon):
    """Implementation of verification checks for the ceph-mon charm."""

    NAME = "ceph-mon"

    @staticmethod
    def _parse_quorum_status(action: Action) -> Tuple[int, Set[str]]:
        """Parse information from `get-quorum-status` action.

        This function will gain *mon_count* and *online_mons* from the action output.
        """
        quorum_status = json.loads(data_from_action(action, "message"))
        know_mons = set(mon["name"] for mon in quorum_status["monmap"]["mons"])
        online_mons = set(quorum_status["quorum_names"])
        return len(know_mons), online_mons

    def check_ceph_cluster_health(self) -> Result:
        """Check Ceph cluster health for unique ceph-mon application."""
        # Get one ceph-mon unit per each application
        app_map = {unit.application: unit for unit in self.units}
        unique_app_units = app_map.values()
        return self.check_cluster_health(*unique_app_units)

    def check_quorum(self) -> Result:
        """Check that the shutdown does not result in <50% mons alive."""
        result = Result()

        action_results = self.run_action_on_all(
            "get-quorum-status", params={"format": "json"}
        )
        affected_hosts = {unit.machine.hostname for unit in self.units}

        for unit_id, action in action_results.items():
            # run this per unit because we might have multiple clusters
            try:
                mon_count, online_mons = self._parse_quorum_status(action)
                mons_after_change = len(online_mons - affected_hosts)
                if mons_after_change <= mon_count // 2:
                    result.add_partial_result(
                        Severity.FAIL,
                        f"Removing unit {unit_id} will lose Ceph mon quorum",
                    )

            except (json.decoder.JSONDecodeError, KeyError) as error:
                logger.error(
                    "Failed to parse quorum status from Action %s. error: %s",
                    action.entity_id,
                    error,
                )
                result.add_partial_result(
                    Severity.FAIL,
                    f"Failed to parse quorum status from action {action.entity_id}.",
                )

        return result or Result(Severity.OK, "Ceph-mon quorum check passed.")

    def check_version(self) -> Result:
        """Check minimum required version of Juju agent.

        Ceph-mon verifier requires that all the units run juju agent >=2.8.10 due to
        reliance on juju.Machine.hostname feature.
        """
        return self.check_minimum_version(Version("2.8.10"), self.units)

    def verify_reboot(self) -> Result:
        """Verify that it's safe to reboot selected ceph-mon units."""
        ceph_version = checks_executor(self.check_version)
        if not ceph_version.success:
            return ceph_version

        return ceph_version + checks_executor(
            self.check_quorum,
            self.check_ceph_cluster_health,
        )

    def verify_shutdown(self) -> Result:
        """Verify that it's safe to shutdown selected units."""
        return self.verify_reboot()
