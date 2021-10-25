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
"""neutron-gateway verification."""

from typing import Any, Dict, List

import yaml
from juju.unit import Unit
from packaging.version import Version

from juju_verify.utils.action import data_from_action
from juju_verify.utils.unit import parse_charm_name, run_action_on_unit
from juju_verify.verifiers.base import BaseVerifier, Result, Severity
from juju_verify.verifiers.result import checks_executor


class NeutronGateway(BaseVerifier):
    """Implementation of verification checks for the neutron-gateway charm."""

    NAME = "neutron-gateway"
    action_name_result_map = {
        "show-routers": "router-list",
        "show-dhcp-networks": "dhcp-networks",
        "show-loadbalancers": "load-balancers",
    }
    action_name_failure_string_map = {
        "show-routers": "The following routers are non-redundant: {}",
        "show-dhcp-networks": "The following DHCP networks are non-redundant: {}",
        "show-loadbalancers": (
            "The following LBaasV2 LBs were found: {}. LBaasV2 does not offer HA."
        ),
    }

    @classmethod
    def get_unit_resource_list(
        cls, unit: Unit, get_resource_action_name: str
    ) -> Dict[str, Dict[str, Any]]:
        """Given a get resource action, return the relevant resources on the unit."""
        get_resource_action = run_action_on_unit(unit, get_resource_action_name)
        action_name_res = cls.action_name_result_map[get_resource_action_name]
        resource_dict_json = data_from_action(get_resource_action, action_name_res)
        resource_dict = yaml.safe_load(resource_dict_json)
        return resource_dict

    def get_all_ngw_units(self) -> List[Unit]:
        """Get all neutron-gateway units, including those not being shutdown."""
        return [
            unit
            for unit in self.model.units.values()
            if parse_charm_name(unit.data.get("charm-url", "")) == self.NAME
        ]

    def get_resource_list(self, get_resource_action_name: str) -> List[dict]:
        """Given a get resource action, return matching resources from all units."""
        resource_list = []
        shutdown_hostname_list = [unit.machine.hostname for unit in self.units]

        for unit in self.get_all_ngw_units():
            hostname = unit.machine.hostname
            host_resource_dict = self.get_unit_resource_list(
                unit, get_resource_action_name
            )

            # add host metadata to resource
            for resource_id, info in host_resource_dict.items():
                resource_list.append(
                    {
                        "id": resource_id,
                        "host": hostname,
                        "juju-entity-id": unit.entity_id,
                        "shutdown": hostname in shutdown_hostname_list,
                        **info,
                    }
                )

        return resource_list

    def get_shutdown_resource_list(self, get_resource_action_name: str) -> List[dict]:
        """Return a list of resources matching action that are going to be shutdown."""
        res_list = self.get_resource_list(get_resource_action_name)
        return [
            resource
            for resource in res_list
            if resource["shutdown"] and resource["status"] == "ACTIVE"
        ]

    def get_online_resource_list(self, get_resource_action_name: str) -> List[dict]:
        """Return a list of resources matching action, that will remain online."""
        res_list = self.get_resource_list(get_resource_action_name)
        return [
            resource
            for resource in res_list
            if not resource["shutdown"] and resource["status"] == "ACTIVE"
        ]

    def check_non_redundant_resource(self, action_name: str) -> Result:
        """Check that there are no non-redundant resources matching the resource type."""
        shutdown_resource_list = self.get_shutdown_resource_list(action_name)
        redundant_resource_list = self.get_online_resource_list(action_name)

        shutdown_resource_set = set(res["id"] for res in shutdown_resource_list)
        redundant_resource_set = set(res["id"] for res in redundant_resource_list)
        non_redundant_list = shutdown_resource_set - redundant_resource_set
        if non_redundant_list:
            failure_string = self.action_name_failure_string_map[action_name]
            reason = failure_string.format(", ".join(non_redundant_list))
            result = Result(Severity.FAIL, reason)
        else:
            resource = self.action_name_result_map[action_name]
            reason = f"Redundancy check passed for: {resource}"
            result = Result(Severity.OK, reason)
        return result

    def warn_router_ha(self) -> Result:
        """Warn that HA routers should be manually failed over."""
        result = Result()
        shutdown_resource_list = self.get_shutdown_resource_list("show-routers")

        router_failover_err_list = []
        for router in shutdown_resource_list:
            if router["ha"]:
                _id = router["id"]
                entity_id = router["juju-entity-id"]
                host = router["host"]
                error_string = f"{_id} (on {entity_id}, hostname: {host})"
                router_failover_err_list.append(error_string)

        if router_failover_err_list:
            error_string = (
                "It's recommended that you manually failover the following "
                "routers: {}"
            )
            reason = error_string.format(", ".join(router_failover_err_list))
            result = Result(Severity.WARN, reason)

        return result

    def warn_lbaas_present(self) -> Result:
        """Warn that LBaasV2 loadbalancers are present on the verified units."""
        result = Result()
        shutdown_lbaas_list = self.get_resource_list("show-loadbalancers")
        units_with_lbaas = {unit["juju-entity-id"] for unit in shutdown_lbaas_list}
        affected_lbaas_units = set(self.unit_ids) & units_with_lbaas

        if affected_lbaas_units:
            message = (
                "Following units have neutron LBaasV2 load-balancers that will be "
                "lost on unit reboot/shutdown: {}"
            )
            reason = message.format(", ".join(affected_lbaas_units))
            result = Result(Severity.WARN, reason)

        return result

    def version_check(self) -> Result:
        """Check minimum required version of Juju agents.

        NeutronGateway verifier requires that all the neutron-gateway units run juju
        agent >=2.8.10 due to reliance on juju.Machine.hostname feature.
        """
        return self.check_minimum_version(Version("2.8.10"), self.get_all_ngw_units())

    def verify_reboot(self) -> Result:
        """Verify that it's safe to reboot selected neutron-gateway units."""
        return self.verify_shutdown()

    def verify_shutdown(self) -> Result:
        """Verify that it's safe to shutdown selected neutron-gateway units."""
        version_check = checks_executor(self.version_check)
        if not version_check.success:
            return version_check

        return version_check + checks_executor(
            self.warn_router_ha,
            self.warn_lbaas_present,
            (self.check_non_redundant_resource, {"action_name": "show-routers"}),
            (self.check_non_redundant_resource, {"action_name": "show-dhcp-networks"}),
        )
