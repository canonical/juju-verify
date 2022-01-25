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
import os
from collections import defaultdict
from typing import Any, Dict, List, NamedTuple, Optional, Set, Tuple

from juju.action import Action
from juju.unit import Unit
from packaging.version import Version

from juju_verify.exceptions import CharmException
from juju_verify.utils.action import data_from_action
from juju_verify.utils.unit import (
    find_unit_by_hostname,
    get_first_active_unit,
    run_action_on_unit,
    run_action_on_units,
    run_command_on_unit,
    verify_charm_unit,
)
from juju_verify.verifiers.base import BaseVerifier
from juju_verify.verifiers.result import Result, Severity, checks_executor

logger = logging.getLogger(__name__)

CEPH_CRUSH_TYPES = {
    # <crush-type>: <crush-type_id>
    "root": 10,
    "region": 9,
    "datacenter": 8,
    "room": 7,
    "pod": 6,
    "pdu": 5,
    "row": 4,
    "rack": 3,
    "chassis": 2,
    "host": 1,
    "osd": 0,
}

CRUSH_RULE_DEVICE_TYPES = {
    "default": None,
    "default~hdd": "hdd",
    "default~ssd": "ssd",
    "default~nvme": "nvme",
}


class CrushRuleInfo(NamedTuple):
    """Information about Node obtains from `ceph osd dump`."""

    id: int
    name: str
    failure_domain: str
    device_class: Optional[str] = None


class PoolInfo(NamedTuple):
    """Information about Node obtains from `ceph osd dump`."""

    id: int
    name: str
    type: int
    size: int
    min_size: int
    crush_rule: CrushRuleInfo
    erasure_code_profile: str


class NodeInfo(NamedTuple):
    """Information about Node obtains from `ceph osd df tree`.

    The `ceph df` [1] comes from ceph-mon unit and it's run with additional option
    `tree` to show output in Crush Map hierarchy format.
    The Crush Map hierarchy [2] contains the following types along with their IDs.

    <type>: <type_id>
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
    device_class: Optional[str] = None

    def __str__(self) -> str:
        """Return representation of the Node as a string."""
        return f"{self.type_id}-{self.name}({self.id})"

    def __hash__(self) -> int:
        """Return hash representation of Node."""
        return hash(self.__str__())


class CephTree:
    """Ceph tree."""

    # list of supported ancestor types (for the host) based on the failure domain in
    # the replication rule, where the ancestor type is the same as the failure domain
    # except for failure-domain=host -> ancestor=root
    SUPPORTED_ANCESTOR_TYPES = [
        "root",
        "region",
        "datacenter",
        "room",
        "pod",
        "pdu",
        "row",
        "rack",
        "chassis",
    ]

    def __init__(self, nodes: List[NodeInfo]):
        """Availability zone initialization.

        The nodes argument comes from the output of the `ceph df osd tree` command
        and consists of NodeInfo.
        All nodes of type `host` have `name` equivalent to machine hostname.
        """
        self._nodes = nodes
        self._nodes_name_map = {node.name: index for index, node in enumerate(nodes)}

    def __eq__(self, other: object) -> bool:
        """Compare two Result instances."""
        if not isinstance(other, CephTree):
            return NotImplemented

        return self.nodes == other._nodes

    def __str__(self) -> str:
        """Return string representation of CephTree objects."""
        return ",".join(
            str(node)
            for node in sorted(self.nodes, key=lambda node: node.type_id, reverse=True)
        )

    def __hash__(self) -> int:
        """Return hash representation of CephTree objects."""
        return hash(self.__str__())

    @property
    def nodes(self) -> List[NodeInfo]:
        """List of nodes in Ceph tree."""
        return self._nodes

    def get_node(self, name: str) -> NodeInfo:
        """Get node by name."""
        if name not in self._nodes_name_map.keys():
            raise KeyError(f"Node {name} was not found.")

        try:
            node = self.nodes[self._nodes_name_map[name]]
            assert node.name == name  # check that variable _nodes was not changed
            return node
        except (IndexError, AssertionError) as error:
            raise ValueError("Private value `_nodes` was changed.") from error

    def find_ancestor(self, node: NodeInfo, required_type: str) -> Optional[NodeInfo]:
        """Find ancestor with the desired type.

        This function will recursively search for the parent node until the parent
        is of the desired type.
        Example:
        {"id": -1, "name": "root", "children": [-2, -3], ...},
        {"id": -2, "name": "rack.0", "children": [-4, -5], ...},
        {"id": -4, "name": "host.0", "children": [0, 1, 2], ...},
        {"id": -5, "name": "host.1", "children": [3, 4, 5], ...},
        ...
        {"id": -3, "name": "rack.1", "children": [-6, -7], ...},
        ...

        The request is to find the `root` ancestor for the `host.0`.
        The first step is to find a parent who has id=-4 among its children, then
        check if it is root. The parent node found is of the rack type with id=-2,
        so the first step is repeated for this node until the parent node is of the
        root type.
        """
        for _node in self.nodes:
            if _node.children and node.id in _node.children:
                if _node.type != required_type:
                    # continue searching for the parent for the currently found node
                    return self.find_ancestor(_node, required_type)

                return _node

        return None

    def can_remove_host_node(
        self, *names: str, required_ancestor_type: str = "root"
    ) -> bool:
        """Check if host node could be removed."""
        if required_ancestor_type not in self.SUPPORTED_ANCESTOR_TYPES:
            raise ValueError(f"`{required_ancestor_type}` is not supported")

        # names allowed are of the type "host", which matches Juju units
        if not all(self.get_node(name).type == "host" for name in names):
            raise ValueError(
                "Function can_remove_host_node is working only for node type host."
            )

        # Finds matching ancestors for host node.
        ancestors_map = defaultdict(list)
        for name in names:
            # NOTE (rgildein): `self.get_node` could raise an error here, but the
            # check runner catches all exceptions.
            descendent = self.get_node(name)
            ancestor = self.find_ancestor(descendent, required_ancestor_type)
            logger.debug("found ancestor `%s` for host node `%s`", ancestor, descendent)
            if ancestor is None:
                raise ValueError(
                    f"An ancestor for the host node {descendent} could not be found."
                )

            ancestors_map[ancestor].append(descendent)

        # Check if all children could be removed from parent.
        for ancestor, descendents in ancestors_map.items():
            # NOTE (rgildein): This will check that the ancestor will have enough space
            # even if the descendent are removed. An example with attempt to remove 2
            # descendents:
            #   parent with 5 children has 1 000 kB free space
            #   each child used the 400 kB space (2 000 kB total)
            #   each child has 200 kB of free space (1 000 kB total)
            #
            #   total available space after removing 2 units: 1 000kB - 2x200kB
            #   the total space that must moved to other units: 2x400kB
            #   check failed, due 600kB <= 800kB
            total_descendent_kb_used = sum(
                descendent.kb_used for descendent in descendents
            )
            total_descendent_kb_avail = sum(
                descendent.kb_avail for descendent in descendents
            )
            if (
                ancestor.kb_avail - total_descendent_kb_avail
            ) <= total_descendent_kb_used:
                logger.debug(
                    "Lack of space %d kB <= %d kB. Children %s cannot be removed.",
                    ancestor.kb_avail,
                    total_descendent_kb_used,
                    ",".join(str(descendent) for descendent in descendents),
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

            if "HEALTH_OK" in cluster_health:
                result.add_partial_result(
                    Severity.OK, f"{unit}: Ceph cluster is healthy"
                )
            elif "HEALTH_WARN" in cluster_health:
                result.add_partial_result(
                    Severity.FAIL,
                    f"{unit}: Ceph cluster is in a warning state{os.linesep}"
                    f"  {cluster_health}",
                )
            elif "HEALTH_ERR" in cluster_health:
                result.add_partial_result(
                    Severity.FAIL,
                    f"{unit}: Ceph cluster is unhealthy{os.linesep}  {cluster_health}",
                )
            else:
                result.add_partial_result(
                    Severity.FAIL,
                    f"{unit}: Ceph cluster is in an unknown state{os.linesep}"
                    f"  {cluster_health}",
                )

        if not action_map:
            result = Result(Severity.FAIL, "Ceph cluster status could not be obtained")

        return result

    @classmethod
    def get_crush_rules(cls, unit: Unit) -> Dict[int, CrushRuleInfo]:
        """Get all crush rules in Ceph cluster."""
        verify_charm_unit("ceph-mon", unit)
        # NOTE (rgildein): This should be replaced be feature action [1] in ceph-mon.
        # [1]: https://bugs.launchpad.net/charm-ceph-mon/+bug/1957458
        action = run_command_on_unit(
            unit, "ceph --id admin osd crush rule dump -f json"
        )
        crush_rule_dump = data_from_action(action, "Stdout")
        # NOTE (rgildein): Need to remove `\n` character. This is from unit, so using
        # os.linesep does not make sense.
        crush_rules_json: List[Dict[str, Any]] = json.loads(
            crush_rule_dump.replace("\n", "")
        )
        crush_rules = {}
        for crush_rule in crush_rules_json:
            crush_rule_info = {
                "id": crush_rule["rule_id"],
                "name": crush_rule["rule_name"],
            }
            for step in crush_rule["steps"]:
                if "type" in step:
                    crush_rule_info["failure_domain"] = step["type"]
                elif "item_name" in step:
                    crush_rule_info["device_class"] = CRUSH_RULE_DEVICE_TYPES[
                        step["item_name"]
                    ]

            crush_rules[crush_rule["rule_id"]] = CrushRuleInfo(**crush_rule_info)

        return crush_rules

    @classmethod
    def get_ceph_pools(cls, unit: Unit) -> List[PoolInfo]:
        """Get detail about Ceph pools (name, type, min_size, replicated).

        This function runs the `list-pools` action with the parameter 'format=json'
        to gather information about all pools.
        Pool types:
        1 - replicated crush rule type is required to know how the data is replicated
        2 - erasure (not supported yet)
        3 - erasure-coded (not supported yet)

        :raises CharmException: if the unit does not belong to the ceph-mon charm
        :raises TypeError: if the object pools is not iterable
        :raises KeyError: if the key could not be obtained from the pool detail
        :raises VerificationError: if any pool is in not supported type
        :raises json.decoder.JSONDecodeError: if json.loads failed
        """
        verify_charm_unit("ceph-mon", unit)
        action = run_action_on_unit(unit, "list-pools", params={"format": "json"})
        action_output = data_from_action(action, "message", "[]")
        logger.debug("parse information about pools: %s", action_output)
        pools: List[Dict[str, Any]] = json.loads(action_output)

        # get all crush rules in Ceph cluster
        crush_rules = cls.get_crush_rules(unit)
        logger.debug("found %d crush rules in Ceph cluster", len(crush_rules))
        return [
            PoolInfo(
                id=pool["pool"],
                name=pool["pool_name"],
                type=pool["type"],
                size=pool["size"],
                min_size=pool["min_size"],
                crush_rule=crush_rules[pool["crush_rule"]],
                erasure_code_profile=pool["erasure_code_profile"],
            )
            for pool in pools
        ]

    @classmethod
    def get_disk_utilization(cls, unit: Unit) -> List[NodeInfo]:
        """Get disk utilization as osd tree output."""
        verify_charm_unit("ceph-mon", unit)
        # NOTE (rgildein): The `show-disk-free` action will provide output w/ 3 keys,
        # while this function uses only one, namely `nodes`.
        # https://github.com/openstack/charm-ceph-mon#actions
        action = run_action_on_unit(unit, "show-disk-free", params={"format": "json"})
        action_output = data_from_action(action, "message", "{}")
        # NOTE (rgildein): The returned output is supported since Ceph v10.2.11 onwards.
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
                device_class=node.get("device_class"),
            )
            for node in osd_tree["nodes"]
        ]


class CephOsd(CephCommon):
    """Implementation of verification checks for the ceph-osd charm."""

    NAME = "ceph-osd"
    # NOTE (rgildein): need to implement replication_rule here, aka need to get this
    # information from pools
    REPLICATION_RULE = "host"

    def __init__(
        self, units: List[Unit], exclude_affected_units: Optional[List[Unit]] = None
    ):
        """Ceph-osd charm verifier."""
        super().__init__(units=units, exclude_affected_units=exclude_affected_units)
        self._ceph_mon_app_map: Optional[Dict[str, Unit]] = None
        self._ceph_tree_map: Optional[Dict[str, CephTree]] = None
        self._units_device_class_map: Optional[Dict[str, Dict[str, Set[Unit]]]] = None

    @property
    def ceph_mon_app_map(self) -> Dict[str, Unit]:
        """Get a map between ceph-osd applications and the first ceph-mon unit.

        :returns: Dictionary with keys as distinct applications of verified units and
                  values as the first ceph-mon unit obtained from the relation with the
                  ceph-mon application (<application_name>:mon).
        """
        if self._ceph_mon_app_map is None:
            self._ceph_mon_app_map = self._get_ceph_mon_app_map()

        if not self._ceph_mon_app_map:
            logger.warning("the relation map between ceph-osd and ceph-mon is empty")

        logger.debug("found ceph-mon application map: %s", self._ceph_mon_app_map)
        return self._ceph_mon_app_map

    @property
    def ceph_tree_map(self) -> Dict[str, CephTree]:
        """Get a map between ceph-osd application and the Ceph tree."""
        if self._ceph_tree_map is None:
            self._ceph_tree_map = self._get_ceph_tree_map()

        if not self._ceph_tree_map:
            logger.warning("could not get Ceph tree map")

        logger.debug("found ceph tree map: %s", str(self._ceph_tree_map))
        return self._ceph_tree_map

    @property
    def units_device_class_map(self) -> Dict[str, Dict[str, Set[Unit]]]:
        """Get a map between ceph-osd units and osds device class.

        Return dictionary contain three keys `hdd`, `ssd` and `nvme` and a set of units.
        """
        if self._units_device_class_map is None:
            self._units_device_class_map = self._get_units_device_class_map()

        if not self._units_device_class_map:
            logger.warning("could not get units device class map")

        logger.debug(
            "found units device class map: %s", str(self._units_device_class_map)
        )
        return self._units_device_class_map

    @property
    def ancestor_node_type(self) -> str:
        """Get ancestor node type based on all crush rules used on pools.

        If the replication rule is set to a host and the goal is to remove the host(s),
        then it is necessary to calculate free space for the entire root. Otherwise, if
        there is a replication rule between the chassis and the region, then it is
        necessary to check the free space on these nodes.
        """
        replication_rule = self.REPLICATION_RULE

        if replication_rule == "host":
            return "root"

        return replication_rule

    def _get_units_device_class_map(self) -> Dict[str, Dict[str, Set[Unit]]]:
        """Get units device class map."""
        # create defaultdict with dictionary contains hdd, ssd and nvme as set
        units_device_class_map: Dict[str, Dict[str, Set[Unit]]] = defaultdict(
            lambda: {"hdd": set(), "ssd": set(), "nvme": set()}
        )
        # iterate over ceph-osd application
        for app, ceph_tree in self.ceph_tree_map.items():
            # get all nodes type host
            hosts = {node for node in ceph_tree.nodes if node.type == "host"}
            # create osd map from all nodes type osd and their ids
            osds = {node.id: node for node in ceph_tree.nodes if node.type == "osd"}

            for host in hosts:
                if not host.children:
                    continue

                # get unit from host.name
                unit = find_unit_by_hostname(self.model, host.name, self.NAME)
                # go through all the children
                for osd_id in host.children:
                    osd = osds.get(osd_id)  # get osd from id
                    if osd is None:
                        logger.warning("could not found osd with `%d` id", osd_id)
                    elif osd.device_class is None:
                        logger.warning("osd with `%d` id has no device class", osd_id)
                    else:
                        units_device_class_map[app][osd.device_class].add(unit)

        return units_device_class_map

    def _get_ceph_tree_map(self) -> Dict[str, CephTree]:
        """Get Ceph tree for each ceph-osd application."""
        return {
            app_name: CephTree(nodes=self.get_disk_utilization(ceph_mon_unit))
            for app_name, ceph_mon_unit in self.ceph_mon_app_map.items()
        }

    def _get_ceph_mon_unit(self, app_name: str) -> Unit:
        """Get first ceph-mon unit from relation."""
        if app_name not in self.model.applications.keys():
            raise CharmException(f"Application {app_name} was not found in model.")

        for relation in self.model.applications[app_name].relations:
            if relation.matches(f"{app_name}:mon"):
                unit = get_first_active_unit(relation.provides.application.units)
                if unit is None:
                    raise CharmException(
                        f"No active unit related to {app_name} application via "
                        f"relation {relation} was found."
                    )

                logger.debug(
                    "found ceph-mon unit `%s` related to ceph-osd application `%s`",
                    unit,
                    app_name,
                )
                return unit

        # if no unit has been returned yet
        raise CharmException(f"No `{app_name}:mon` relation was found.")

    def _get_ceph_mon_app_map(self) -> Dict[str, Unit]:
        """Get first ceph-mon units related to verified units.

        This function groups by distinct application names for verified units, and then
        finds the relation ("<application>:mon") between the application and ceph-mon.
        The first unit of ceph-mon will be obtained from this relation.
        :returns: Map between verified and ceph-mon units
        """
        applications = {unit.application for unit in self.units}
        logger.debug("affected applications %s", ", ".join(applications))
        return {name: self._get_ceph_mon_unit(name) for name in applications}

    def _get_units_by_device_class(self, app_name: str, pool: PoolInfo) -> Set[Unit]:
        """Get all units that contain at least one device class OSD as pool.

        This function will get all units for specific application and then filters
        the units that contain an OSD with the same device class as the pool. Finally,
        it filters only active units and those for which the check is performed
        (self.units).
        """
        units_device_class_map = self.units_device_class_map[app_name]
        # get all ceph-osd units, that contain at least one osd with device
        # class same as crush rule in pool
        if pool.crush_rule.device_class is not None:
            all_units = units_device_class_map[pool.crush_rule.device_class]
        else:
            # NOTE (rgildein): If device_class is None, it means all osd will be used.
            # The device_class is set automatically on ODDs startup [1] and could be
            # set only to hdd, ssd and nvme [2].
            # [1]: https://docs.ceph.com/en/latest/rados/operations/crush-map/#device-classes # noqa: E501 pylint: disable=C0301
            # [2]: https://docs.ceph.com/en/latest/rados/operations/crush-map/#devices
            all_units = set().union(
                units_device_class_map["hdd"],
                units_device_class_map["ssd"],
                units_device_class_map["nvme"],
            )

        logger.debug(
            "found %d units that have an osd type %s",
            len(all_units),
            pool.crush_rule.device_class,
        )
        # filter active units and units out of self.units
        units = {
            unit
            for unit in all_units
            if unit.entity_id not in self.unit_ids and unit.workload_status == "active"
        }
        logger.debug("%d units remain active after reboot/shutdown", len(units))

        return units

    @staticmethod
    def _count_branch(tree: CephTree, units: Set[Unit], root_type: str) -> int:
        """Count unique branches for list of units (hots) in Ceph Tree."""
        if root_type == "host":
            return len(units)

        ancestors = set()
        for unit in units:
            node = tree.get_node(unit.machine.hostname)
            ancestor = tree.find_ancestor(node, root_type)
            if ancestor is None:
                raise CharmException(f"Could nod find ancestors for node `{node.name}`")

            logging.debug("Found ancestor %s for unit %s", ancestor, unit)
            ancestors.add(ancestor)

        return len(ancestors)

    def check_ceph_pools(self) -> Result:
        """Check whether Ceph cluster pools meet the requirements."""
        for ceph_mon_unit in self.ceph_mon_app_map.values():
            pools = self.get_ceph_pools(ceph_mon_unit)

            # 1: replicated,
            # 2: erasure (not supported yet)
            # 3: erasure-coded (not supported yet)
            if any(pool.type != 1 for pool in pools):
                return Result(
                    Severity.FAIL,
                    "Juju-verify only supports the replicated pool for now.",
                )

            if len({pool.crush_rule.failure_domain for pool in pools}) > 1:
                return Result(
                    Severity.FAIL,
                    "Juju-verify only supports crush rules with same failure-domain "
                    "for now.",
                )

        return Result(Severity.OK, "The requirements for ceph check were met.")

    def check_ceph_cluster_health(self) -> Result:
        """Check Ceph cluster health for unique ceph-mon units from ceph_mon_app_map."""
        unique_ceph_mon_units = {
            unit.entity_id: unit for unit in self.ceph_mon_app_map.values()
        }
        return self.check_cluster_health(*unique_ceph_mon_units.values())

    def check_replication_number(self) -> Result:
        """Check the minimum number of replications for related applications."""
        result = Result()

        for app_name, ceph_mon_unit in self.ceph_mon_app_map.items():
            ceph_tree = self.ceph_tree_map[app_name]
            for pool in self.get_ceph_pools(ceph_mon_unit):
                # get all units that contain OSD with the same device class as the pool
                units = self._get_units_by_device_class(app_name, pool)
                # count failure_domains
                count_remaining_failure_domains = self._count_branch(
                    ceph_tree, units, pool.crush_rule.failure_domain
                )
                logger.debug(
                    "%d %s(s) failure domain remain active after reboot/shutdown",
                    count_remaining_failure_domains,
                    pool.crush_rule.failure_domain,
                )

                if count_remaining_failure_domains < pool.min_size:
                    affected_units = {
                        unit.entity_id
                        for unit in self.units
                        if unit.application == app_name
                    }
                    result.add_partial_result(
                        Severity.FAIL,
                        f"The minimum number of replicas in `{app_name}` and pool "
                        f"`{pool.name}` is {pool.min_size:d} and it's not safe to "
                        f"reboot/shutdown {', '.join(affected_units)} units.",
                    )

        return result or Result(Severity.OK, "Minimum replica number check passed.")

    def check_availability_zone(self) -> Result:
        """Check availability zones resources.

        This function checks whether the units can be reboot/shutdown without
        interrupting operation in the availability zone.
        """
        result = Result()
        for ceph_osd_app, ceph_tree in self.ceph_tree_map.items():
            units = {
                unit.entity_id: unit.machine.hostname
                for unit in self.units
                if unit.application == ceph_osd_app
            }

            if not ceph_tree.can_remove_host_node(
                *units.values(), required_ancestor_type=self.ancestor_node_type
            ):
                units_to_remove = ", ".join(units.keys())
                result += Result(
                    Severity.FAIL,
                    f"It's not safe to reboot/shutdown unit(s) {units_to_remove} in "
                    f"the availability zone '{ceph_tree}'.",
                )

        return result or Result(Severity.OK, "Availability zone check passed.")

    def verify_reboot(self) -> Result:
        """Verify that it's safe to reboot selected ceph-osd units."""
        ceph_pools_check = checks_executor(self.check_ceph_pools)
        if not ceph_pools_check.success:
            return ceph_pools_check

        return ceph_pools_check + checks_executor(
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
        unique_units = {unit.entity_id: unit for unit in app_map.values()}
        return self.check_cluster_health(*unique_units.values())

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
                        f"Rebooting or shutting down the unit {unit_id} will lose "
                        f"ceph-mon quorum",
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
