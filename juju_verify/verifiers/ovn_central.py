# Copyright 2022 Canonical Limited.
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
"""ovn-central verification."""
import asyncio
import logging
import os
from collections import defaultdict
from typing import Any, Dict, List, NamedTuple, Optional

import yaml
from juju.unit import Unit

from juju_verify.exceptions import JujuVerifyError
from juju_verify.utils.action import data_from_action
from juju_verify.utils.unit import run_action_on_units
from juju_verify.verifiers.base import BaseVerifier
from juju_verify.verifiers.result import Result, Severity, checks_executor

logger = logging.getLogger(__name__)

StatusCollectionType = Dict[str, "UnitClusterStatus"]


class ClusterStatus:  # pylint: disable=R0902
    """Object representation of OVN cluster status.

    Attributes of this object represent status of a single (Southbound or Northbound)
    cluster as retrieved from 'cluster-status' action of ovn-central charm unit. Example
    of an input data for initialization of this class:

    .. code-block:: yaml

        Cluster ID: 567e7225-369e-40d6-abf8-9b442bbcd18b
        Server ID: 16335def-c21e-404c-b123-8337b3013c07
        Address: ssl:10.5.2.232:6644
        Status: cluster member
        Role: follower
        Term: 34
        Leader: dbdb
        Vote: dbdb
        Log: '[66, 66]'
        Entries not yet committed: 0
        Entries not yet applied: 0
        Servers:
        - - 7f23
          - ssl:10.75.224.151:6644
        - - 1bc5
          - ssl:10.75.224.192:6644
        - - 1ef7
          - ssl:10.75.224.120:6644
        unit_map:
          ovn-central/0: 7f23
          ovn-central/1: 1bc5
          ovn-central/2: 1ef7
    """

    def __init__(self, raw_status: str) -> None:
        """Initialize Cluster status class.

        For more info about the purpose and input data format see class documentation.

        :param raw_status: YAML string containing status of a single OVN cluster.
        """
        try:
            status_dict = yaml.safe_load(raw_status)
            if not isinstance(status_dict, dict):
                raise ValueError("Input data is not a YAML dictionary.")
        except (yaml.YAMLError, ValueError) as exc:
            raise JujuVerifyError(
                f"Failed to load OVN status as YAML:{os.linesep}{raw_status}"
            ) from exc

        try:
            self.cluster_id = status_dict["cluster_id"]
            self.server_id = status_dict["server_id"]
            self.address = status_dict["address"]
            self.status = status_dict["status"]
            self.role = status_dict["role"]
            self.term = status_dict["term"]
            self.leader = status_dict["leader"]
            self.vote = status_dict["vote"]
            self.log = status_dict["log"]
            self.entries_not_yet_committed = status_dict["entries_not_yet_committed"]
            self.entries_not_yet_applied = status_dict["entries_not_yet_applied"]
            self.servers = status_dict["servers"]
            self.unit_map = status_dict["unit_map"]

        except KeyError as exc:
            raise JujuVerifyError(
                f"Failed to deserialize OVN cluster status. Missing "
                f"'{exc.args[0]}' from cluster status data."
            ) from exc

    @property
    def short_id(self) -> str:
        """Return first 4 characters of a Server ID.

        This format is often used to refer to servers within cluster instead of full ID.
        """
        return self.server_id[:4]

    @property
    def is_leader(self) -> bool:
        """Return true if Server that reported this status consider itself a leader."""
        return self.leader == "self"

    def __eq__(self, other: Any) -> bool:
        """Implement equality comparison for ClusterStatus instances."""
        if not isinstance(other, ClusterStatus):
            return NotImplemented

        comparable_attrs = [
            "cluster_id",
            "server_id",
            "address",
            "status",
            "role",
            "term",
            "leader",
            "vote",
            "log",
            "entries_not_yet_committed",
            "entries_not_yet_applied",
            "servers",
            "unit_map",
        ]
        equal = True
        try:
            for attr in comparable_attrs:
                if self.__getattribute__(attr) != other.__getattribute__(attr):
                    equal = False
                    break
        except AttributeError:
            equal = False

        return equal


class UnitClusterStatus(NamedTuple):
    """Convenience class that groups Southbound and Northbound cluster status.

    This is how a single ovn-central unit views status of these clusters.
    """

    southbound: ClusterStatus
    northbound: ClusterStatus

    def __eq__(self, other: Any) -> bool:
        """Implement equality comparison between UnitClusterStatus instances."""
        if not isinstance(other, UnitClusterStatus):
            return NotImplemented

        return (
            self.southbound == other.southbound and self.northbound == other.northbound
        )


class OvnCentral(BaseVerifier):
    """Implementation of verification checks for the ovn-central charm."""

    NAME = "ovn-central"

    def __init__(
        self, units: List[Unit], exclude_affected_units: Optional[List[Unit]] = None
    ):
        """Initialize ovn-central charm verifier."""
        super().__init__(units, exclude_affected_units)
        self._complete_cluster_status: StatusCollectionType = {}
        self._all_application_units: List[Unit] = []

    @property
    def complete_cluster_status(self) -> StatusCollectionType:
        """Collect and return status of a cluster from every ovn-central unit.

        This method collects Southbound and Northbound cluster status reports from every
        unit that belongs to an application of currently verified unit(s).
        """
        report_err = (
            "{} failed to report {} cluster status. Please try to run "
            "`cluster-status` action manually."
        )
        if not self._complete_cluster_status:
            action_results = run_action_on_units(
                self.all_application_units, "cluster-status", use_cache=False
            )
            for unit_name, result in action_results.items():
                sb_data = data_from_action(result, "ovnsb")
                nb_data = data_from_action(result, "ovnnb")
                if not sb_data:
                    raise JujuVerifyError(report_err.format(unit_name, "Southbound"))
                if not nb_data:
                    raise JujuVerifyError(report_err.format(unit_name, "Northbound"))

                self._complete_cluster_status[unit_name] = UnitClusterStatus(
                    southbound=ClusterStatus(sb_data), northbound=ClusterStatus(nb_data)
                )

        return self._complete_cluster_status

    @property
    def all_application_units(self) -> List[Unit]:
        """Return list of all units from an application of currently verified unit(s)."""
        if not self._all_application_units:
            app = self.units[0].application
            self._all_application_units = [
                unit for unit in self.model.units.values() if unit.application == app
            ]
        return self._all_application_units

    @staticmethod
    def cluster_tolerance(size: int) -> int:
        """Return number of failed nodes that the cluster can tolerate.

        This calculation is based on the raft protocol's requirement to have "(N/2) + 1"
        active nodes to maintain quorum.

        :param size: Current size of a cluster.
        :return: Number of nodes that can fail without loosing cluster quorum
        """
        if size < 1:
            return 0

        min_quorum_size = (size // 2) + 1
        return size - min_quorum_size

    def check_single_application(self) -> Result:
        """Verify that all units that are being verified belong to the same app."""
        apps = {unit.application for unit in self.units}
        if len(apps) > 1:
            app_list = ", ".join(apps)
            return Result(
                Severity.FAIL,
                f"Can't verify multiple ovn-central application at the same time. "
                f"Currently selected units belong to: {app_list}",
            )

        return Result(Severity.OK, "Selected units are part of only one application.")

    def check_leader_consistency(self) -> Result:
        """Verify consistency of ovn-central cluster."""
        result = Result()
        leader_mappings: Dict[str, Dict[str, List[str]]] = {
            "Southbound": defaultdict(list),
            "Northbound": defaultdict(list),
        }
        for unit, cluster_data in self.complete_cluster_status.items():
            clusters = [
                ("Southbound", cluster_data.southbound),
                ("Northbound", cluster_data.northbound),
            ]
            for cluster_name, status in clusters:
                # Collect opinions on who is the leader from each unit
                leader = status.short_id if status.is_leader else status.leader
                if leader:
                    leader_mappings[cluster_name][leader].append(unit)

        # Verify that there's consensus on who is the cluster leader
        for cluster, leaders in leader_mappings.items():
            if len(leaders) > 1:
                leader_err = f"There's no consensus on {cluster} cluster leader. "
                for leader, units in leaders.items():
                    unit_list = ", ".join(units)
                    leader_err += f"{leader} is supported by {unit_list}; "
                result.add_partial_result(Severity.FAIL, leader_err)
            elif len(leaders) < 1:
                result.add_partial_result(
                    Severity.FAIL,
                    f"No unit reported elected leader in {cluster} cluster.",
                )
            else:
                leader = list(leaders.keys())[0]
                result.add_partial_result(
                    Severity.OK, f"All units agree that {leader} is {cluster} leader."
                )

        return result

    def check_uncommitted_logs(self) -> Result:
        """Verify that there are no uncommitted log entries on cluster leaders."""
        result = Result()
        for unit, cluster_data in self.complete_cluster_status.items():
            clusters = [
                ("Southbound", cluster_data.southbound),
                ("Northbound", cluster_data.northbound),
            ]
            for cluster_name, status in clusters:
                # Verify that cluster leader does not have any uncommitted entries
                if status.is_leader:
                    commits_ok = not bool(status.entries_not_yet_committed)
                    result_severity = Severity.OK if commits_ok else Severity.FAIL
                    result.add_partial_result(
                        result_severity,
                        f"{unit} ({cluster_name} leader) reports "
                        f"{status.entries_not_yet_committed} uncommitted log entries.",
                    )

        return result

    def check_unknown_servers(self) -> Result:
        """Verify that there are no servers in cluster without associated unit.

        This situation can happen if, for example, a unit is removed from the
        application, but it's unable to gracefully leave cluster.
        """
        # For this check, we don't need to go through ClusterStatus of every unit.
        # We can just randomly pick one.
        result = Result()
        err_msg = "{} cluster reports servers that are not associated with a unit."
        cluster_status = self.complete_cluster_status[self.unit_ids[0]]
        if "UNKNOWN" in cluster_status.southbound.unit_map:
            result.add_partial_result(Severity.FAIL, err_msg.format("Southbound"))

        if "UNKNOWN" in cluster_status.northbound.unit_map:
            result.add_partial_result(Severity.FAIL, err_msg.format("Northbound"))

        return result or Result(
            Severity.OK, "No disassociated cluster members reported."
        )

    def check_supported_charm_version(self) -> Result:
        """Verify that targeted application has required actions.

        This verifier requires action "cluster-status" to be present on the charm.
        """
        loop = asyncio.get_event_loop()
        app_name = self.units[0].application
        app = self.model.applications[app_name]
        all_actions = loop.run_until_complete(app.get_actions())
        if "cluster-status" in all_actions.keys():
            return Result(Severity.OK, "Charm supports all required actions.")

        return Result(
            Severity.FAIL,
            "Charm does not support required action 'cluster-status'. Please try "
            "upgrading charm.",
        )

    def check_reboot(self) -> Result:
        """Check that it's safe to temporarily bring down selected units.

        This check verifies that rebooting selected units won't bring the cluster below
        its fault tolerance.
        """
        result = Result()
        all_units = len(self.all_application_units)
        fault_tolerance = self.cluster_tolerance(all_units)
        units_to_reboot = len(self.units)

        if units_to_reboot > fault_tolerance:
            result.add_partial_result(
                Severity.FAIL,
                f"OVN cluster with {all_units} units can not tolerate simultaneous "
                f"reboot of {units_to_reboot} units.",
            )
        else:
            result.add_partial_result(
                Severity.OK,
                f"OVN cluster with {all_units} units can safely tolerate simultaneous "
                f"reboot of {units_to_reboot} units.",
            )
            if units_to_reboot == fault_tolerance:
                result.add_partial_result(
                    Severity.WARN,
                    "While the rebooted units are down, this cluster won't be able to "
                    "tolerate any more failures.",
                )

        return result

    def check_downscale(self) -> Result:
        """Check that removing selected units won't affect cluster's fault tolerance."""
        all_units = len(self.all_application_units)
        units_to_remove = len(self.units)
        original_tolerance = self.cluster_tolerance(all_units)
        post_removal_tolerance = self.cluster_tolerance(all_units - units_to_remove)
        base_msg = f"Removing {units_to_remove} units from cluster of {all_units} "

        if original_tolerance < 1:
            return Result(
                Severity.FAIL,
                f"Cluster of {all_units} units has already 0 fault tolerance.",
            )

        if post_removal_tolerance < 1:
            return Result(
                Severity.FAIL, base_msg + "would bring its fault tolerance to 0."
            )

        if original_tolerance != post_removal_tolerance:
            return Result(
                Severity.WARN,
                base_msg
                + f"will decrease its fault tolerance from {original_tolerance}"
                f" to {post_removal_tolerance}.",
            )

        return Result(Severity.OK, base_msg + "won't impact its fault tolerance.")

    def preflight_checks(self) -> Result:
        """Run common checks that verify integrity of the OVN cluster.

        These checks should be prerequisite before any further checks are run for both
        reboot and shutdown actions
        """
        charm_supported = checks_executor(self.check_supported_charm_version)
        if not charm_supported.success:
            return charm_supported

        return charm_supported + checks_executor(
            self.check_single_application,
            self.check_leader_consistency,
            self.check_uncommitted_logs,
            self.check_unknown_servers,
        )

    def verify_reboot(self) -> Result:
        """Verify that it's safe to reboot selected ovn-central units."""
        preflight_results = self.preflight_checks()
        if not preflight_results.success:
            return preflight_results

        return preflight_results + checks_executor(self.check_reboot)

    def verify_shutdown(self) -> Result:
        """Verify that it's safe to shut down selected ovn-central units."""
        preflight_results = self.preflight_checks()
        if not preflight_results.success:
            return preflight_results

        return preflight_results + checks_executor(self.check_downscale)
