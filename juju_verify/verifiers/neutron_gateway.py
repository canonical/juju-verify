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
import json
from typing import Dict, List

from juju.unit import Unit

from juju_verify.verifiers.base import BaseVerifier, Result, Severity
from juju_verify.verifiers.result import aggregate_results
from juju_verify.utils.action import data_from_action
from juju_verify.utils.unit import parse_charm_name, run_action_on_unit


def get_unit_hostname(unit: Unit) -> str:
    """Return name of the host on which the unit is running."""
    get_hostname_action = run_action_on_unit(unit, "node-name")
    hostname = data_from_action(get_hostname_action, "node-name")
    return hostname


def get_unit_resource_list(unit: Unit, get_resource_action_name: str) -> List[dict]:
    """Given a get resource action, return the relevant resources on the unit."""
    get_resource_action = run_action_on_unit(unit, get_resource_action_name)
    action_name_res = NeutronGateway.action_name_result_map[get_resource_action_name]
    resource_list_json = data_from_action(get_resource_action, action_name_res)
    resource_list = json.loads(resource_list_json)
    return resource_list


class NeutronGateway(BaseVerifier):
    """Implementation of verification checks for the neutron-gateway charm."""

    NAME = 'neutron-gateway'
    action_name_result_map = {"get-status-routers": "router-list",
                              "get-status-dhcp": "dhcp-networks",
                              "get-status-lb": "load-balancers"}
    action_name_failure_string_map = {"get-status-routers": ("The following routers are "
                                                             "non-redundant: {}"),
                                      "get-status-dhcp": ("The following DHCP networks "
                                                          "are non-redundant: {}"),
                                      "get-status-lb": ("The following LBaasV2 LBs were "
                                                        "found: {}. LBaasV2 does not "
                                                        "offer HA.")}

    def __init__(self, units: List[Unit]) -> None:
        """Neutron Gateway verifier constructor."""
        super().__init__(units)
        self.cache_action_resource_list_map: Dict[str, List] = {}

    def get_all_ngw_units(self) -> List[Unit]:
        """Get all neutron-gateway units, including those not being shutdown."""
        all_ngw_units = []
        for unit in self.model.units.values():
            charm = parse_charm_name(unit.data.get('charm-url', ''))
            if charm == self.NAME:
                all_ngw_units.append(unit)
        return all_ngw_units

    def get_resource_list(self, get_resource_action_name: str) -> List[dict]:
        """Given a get resource action, return matching resources from all units."""
        try:
            return self.cache_action_resource_list_map[get_resource_action_name]
        except KeyError:
            pass

        resource_list = []
        shutdown_hostname_list = [get_unit_hostname(unit) for unit in self.units]

        for unit in self.get_all_ngw_units():
            hostname = get_unit_hostname(unit)
            host_resource_list = get_unit_resource_list(unit,
                                                        get_resource_action_name)

            # add host metadata to resource
            for resource in host_resource_list:
                resource["host"] = hostname
                resource["juju-entity-id"] = unit.entity_id
                resource["shutdown"] = False

                if hostname in shutdown_hostname_list:
                    resource["shutdown"] = True

                resource_list.append(resource)

        self.cache_action_resource_list_map[get_resource_action_name] = resource_list
        return resource_list

    def get_shutdown_resource_list(self, get_resource_action_name: str) -> List[dict]:
        """Return a list of resources matching action that are going to be shutdown."""
        res_list = self.get_resource_list(get_resource_action_name)
        return [r for r in res_list if r["shutdown"] and r["status"] == "ACTIVE"]

    def get_online_resource_list(self, get_resource_action_name: str) -> List[dict]:
        """Return a list of resources matching action, that will remain online."""
        res_list = self.get_resource_list(get_resource_action_name)
        return [r for r in res_list if not r["shutdown"] and r["status"] == "ACTIVE"]

    def check_non_redundant_resource(self, action_name: str) -> Result:
        """Check that there are no non-redundant resources matching the resource type."""
        shutdown_resource_list = self.get_shutdown_resource_list(action_name)
        redundant_resource_list = self.get_online_resource_list(action_name)

        shutdown_resource_set = set(r["id"] for r in shutdown_resource_list)
        redundant_resource_set = set(r["id"] for r in redundant_resource_list)
        non_redundant_list = shutdown_resource_set - redundant_resource_set
        if non_redundant_list:
            failure_string = self.action_name_failure_string_map[action_name]
            reason = failure_string.format(", ".join(non_redundant_list))
            result = Result(Severity.FAIL, reason)
        else:
            resource = self.action_name_result_map[action_name]
            reason = "Redundancy check passed for: {}".format(resource)
            result = Result(Severity.OK, reason)
        return result

    def warn_router_ha(self) -> Result:
        """Warn that HA routers should be manually failed over."""
        action_name = "get-status-routers"
        result = Result()
        shutdown_resource_list = self.get_shutdown_resource_list(action_name)

        router_failover_err_list = []
        for router in shutdown_resource_list:
            if router["ha"]:
                _id = router["id"]
                entity_id = router["juju-entity-id"]
                host = router["host"]
                error_string = "{} (on {}, hostname: {})".format(_id, entity_id, host)
                router_failover_err_list.append(error_string)

        if router_failover_err_list:
            error_string = ("It's recommended that you manually failover the following "
                            "routers: {}")
            reason = error_string.format(", ".join(router_failover_err_list))
            result = Result(Severity.WARN, reason)

        return result

    def warn_lbaas_present(self) -> Result:
        """Warn that LBaasV2 loadbalancers are present on the verified units."""
        action_name = "get-status-lb"
        result = Result()
        shutdown_lbaas_list = self.get_resource_list(action_name)
        units_with_lbaas = {unit["juju-entity-id"] for unit in shutdown_lbaas_list}
        affected_lbaas_units = set(self.unit_ids) & units_with_lbaas

        if affected_lbaas_units:
            message = ('Following units have neutron LBaasV2 load-balancers that will be'
                       ' lost on unit shutdown: {}')
            reason = message.format(", ".join(affected_lbaas_units))
            result = Result(Severity.WARN, reason)

        return result

    def verify_reboot(self) -> Result:
        """Verify that it's safe to reboot selected neutron-gateway units."""
        return self.verify_shutdown()

    def verify_shutdown(self) -> Result:
        """Verify that it's safe to shutdown selected neutron-gateway units."""
        return aggregate_results(self.warn_router_ha(),
                                 self.warn_lbaas_present(),
                                 self.check_non_redundant_resource("get-status-routers"),
                                 self.check_non_redundant_resource("get-status-dhcp")
                                 )
