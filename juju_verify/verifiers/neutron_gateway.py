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

from juju_verify.verifiers.base import BaseVerifier, Result
from juju_verify.verifiers.result import aggregate_results
from juju_verify.utils.action import data_from_action
from juju_verify.utils.unit import run_action_on_unit


def get_unit_hostname(unit):
    """Return name of the host on which the unit is running."""
    get_hostname_action = run_action_on_unit(unit, "node-name")
    hostname = data_from_action(get_hostname_action, "node-name")
    return hostname


class NeutronGateway(BaseVerifier):
    """Implementation of verification checks for the neutron-gateway charm."""

    NAME = 'neutron-gateway'
    action_name_result_map = {"get-status-routers": "router-list",
                              "get-status-dhcp": "dhcp-networks",
                              "get-status-lb": "load-balancers"}

    def __init__(self, *args, **kwargs):
        """Neutron Gateway verifier constructor."""
        super().__init__(*args, **kwargs)
        self.cache_action_resource_list_map = {}

    def get_all_ngw_units(self):
        """Get all neutron-gateway units, including those not being shutdown."""
        application_name = NeutronGateway.NAME
        for rel in self.model.relations:
            if rel.matches("{}:cluster".format(application_name)):
                application = rel.applications.pop()
                all_ngw_units = application.units
        return all_ngw_units

    def get_unit_resource_list(self, u, get_resource_action_name):
        """Given a get resource action, return the relevant resources on the unit."""
        get_resource_action = run_action_on_unit(u, get_resource_action_name)
        action_name_res = NeutronGateway.action_name_result_map[get_resource_action_name]
        resource_list_json = data_from_action(get_resource_action, action_name_res)
        resource_list = json.loads(resource_list_json)
        return resource_list

    def get_resource_list(self, get_resource_action_name):
        """Given a get resource action, return matching resources from all units."""
        try:
            return self.cache_action_resource_list_map[get_resource_action_name]
        except KeyError:
            pass

        resource_list = []
        shutdown_hostname_list = [get_unit_hostname(unit) for unit in self.units]

        for u in self.get_all_ngw_units():
            hostname = get_unit_hostname(u)
            host_resource_list = self.get_unit_resource_list(u, get_resource_action_name)

            # add host metadata to resource
            for resource in host_resource_list:
                resource["host"] = hostname
                resource["juju-entity-id"] = u.entity_id
                resource["shutdown"] = False

                if hostname in shutdown_hostname_list:
                    resource["shutdown"] = True

                resource_list.append(resource)

        self.cache_action_resource_list_map[get_resource_action_name] = resource_list
        return resource_list

    def get_shutdown_resource_list(self, get_resource_action_name):
        """Return a list of resources matching action that are going to be shutdown."""
        res_list = self.get_resource_list(get_resource_action_name)
        return [r for r in res_list if r["shutdown"] and r["status"] == "ACTIVE"]
