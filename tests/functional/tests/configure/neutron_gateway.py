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
"""Configuration scripts for juju models related to neutron-gateway charm."""

from neutronclient.v2_0.client import Client
from zaza.openstack.utilities import openstack


def distribute_router(router_id: str, neutron: Client):
    """Make router redundant by spreading it to every available L3 agent."""
    all_agents = neutron.list_agents(agent_type="L3 agent").get("agents", [])
    hosting_agents = neutron.list_l3_agent_hosting_routers(router_id).get("agents", [])

    all_agent_ids = {agent["id"] for agent in all_agents}
    hosting_agent_ids = {agent["id"] for agent in hosting_agents}
    missing_agents = all_agent_ids - hosting_agent_ids

    if missing_agents:
        # Ensure that router has 'ha' enabled
        neutron.update_router(router_id, {"router": {"admin_state_up": False}})
        neutron.update_router(router_id, {"router": {"ha": True}})
        neutron.update_router(router_id, {"router": {"admin_state_up": True}})

        # add router to every l3 agent that does not have it yet
        for agent in missing_agents:
            neutron.add_router_to_l3_agent(agent, {"router_id": router_id})


def distribute_network(network_id: str, neutron: Client):
    """Make network redundant by spreading it to every available DHCP agent."""
    all_agents = neutron.list_agents(agent_type="DHCP agent").get("agents", [])
    hosting_agents = neutron.list_dhcp_agent_hosting_networks(network_id).get(
        "agents", []
    )

    all_agent_ids = {agent["id"] for agent in all_agents}
    hosting_agent_ids = {agent["id"] for agent in hosting_agents}
    agents_not_hosting = all_agent_ids - hosting_agent_ids

    for agent in agents_not_hosting:
        neutron.add_network_to_dhcp_agent(agent, {"network_id": network_id})


def setup_ha_routers():
    """Make sure that every neutron router is redundant."""
    keystone = openstack.get_overcloud_keystone_session()
    neutron_client: Client = openstack.get_neutron_session_client(keystone)

    router_list = neutron_client.list_routers().get("routers", [])
    for router in router_list:
        distribute_router(router["id"], neutron_client)


def setup_ha_networks():
    """Make sure that every neutron network is redundant."""
    keystone = openstack.get_overcloud_keystone_session()
    neutron_client: Client = openstack.get_neutron_session_client(keystone)

    networks = neutron_client.list_networks().get("networks", [])
    for network in networks:
        id_ = network["id"]
        distribute_network(id_, neutron_client)
