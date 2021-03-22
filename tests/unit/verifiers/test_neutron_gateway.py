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
"""NeutronGateway verifier class test suite."""
from unittest import mock
from unittest.mock import MagicMock

from juju.unit import Unit

from juju_verify.verifiers import NeutronGateway

all_ngw_units = []
for i in range(3):
    ngw = MagicMock()
    ngw.entity_id = "neutron-gateway/{}".format(i)
    all_ngw_units.append(ngw)

mock_data = [
    {
        "host": "host0",
        "shutdown": True,
        "unit": all_ngw_units[0],
        "routers": [{"id": "router0", "ha": False, "status": "ACTIVE"},
                    {"id": "router1", "ha": False, "status": "ACTIVE"}]
    },
    {
        "host": "host1",
        "shutdown": False,
        "unit": all_ngw_units[1],
        "routers": [{"id": "router2", "ha": False, "status": "ACTIVE"}],
    },
    {
        "host": "host2",
        "shutdown": False,
        "unit": all_ngw_units[2],
        "routers": [{"id": "router3", "ha": False, "status": "ACTIVE"},
                    {"id": "router4", "ha": False, "status": "ACTIVE"}],
    },
]

all_ngw_host_names = [h["host"] for h in mock_data]

model = MagicMock()


def get_ngw_verifier():
    """Get new NeutronGateway verifier (used for applying changes in shutdown list)."""
    return NeutronGateway([Unit(h["unit"].entity_id, model)
                           for h in mock_data if h["shutdown"]])


def get_resource_lists():
    """Get all routers in mock data."""
    return [h["routers"] for h in mock_data]


def get_shutdown_host_name_list():
    """Get all hostnames of all hosts being shutdown."""
    return [h["host"] for h in mock_data if h["shutdown"]]


def set_router_status(routerid, status):
    """Set status of given router id in mock data."""
    for host in mock_data:
        for router in host["routers"]:
            if router["id"] == routerid:
                router["status"] = status


@mock.patch("juju_verify.verifiers.neutron_gateway.get_unit_resource_list")
@mock.patch("juju_verify.verifiers.neutron_gateway.NeutronGateway.get_all_ngw_units")
@mock.patch("juju_verify.verifiers.neutron_gateway.get_unit_hostname")
def test_get_resource_list(mock_get_unit_hostname,
                           mock_get_all_ngw_units,
                           mock_get_unit_resource_list):
    """Test list of resources returned by get_resource_list."""
    mock_get_unit_hostname.side_effect = (get_shutdown_host_name_list() +
                                          all_ngw_host_names)
    mock_get_all_ngw_units.return_value = all_ngw_units
    mock_get_unit_resource_list.side_effect = get_resource_lists()

    ngw_verifier = get_ngw_verifier()
    router_list = ngw_verifier.get_resource_list("get-status-routers")

    router_count = 0
    for host in mock_data:
        router_count += len(host["routers"])
    assert len(router_list) == router_count


@mock.patch("juju_verify.verifiers.neutron_gateway.get_unit_resource_list")
@mock.patch("juju_verify.verifiers.neutron_gateway.NeutronGateway.get_all_ngw_units")
@mock.patch("juju_verify.verifiers.neutron_gateway.get_unit_hostname")
def test_get_shutdown_resource_list(mock_get_unit_hostname,
                                    mock_get_all_ngw_units,
                                    mock_get_unit_resource_list):
    """Test validity of list of resources to be shutdown."""
    mock_get_unit_hostname.side_effect = (get_shutdown_host_name_list() +
                                          all_ngw_host_names)
    mock_get_all_ngw_units.return_value = all_ngw_units
    mock_get_unit_resource_list.side_effect = get_resource_lists()

    ngw_verifier = get_ngw_verifier()

    router_shutdown_count = 0
    for host in mock_data:
        if host["shutdown"]:
            router_shutdown_count += len(host["routers"])

    shutdown_routers = ngw_verifier.get_shutdown_resource_list("get-status-routers")
    assert len(shutdown_routers) == router_shutdown_count

    # test that inactive resources are not being listed as being shutdown
    set_router_status("router0", "NOTACTIVE")

    mock_get_unit_hostname.side_effect = (get_shutdown_host_name_list() +
                                          all_ngw_host_names)
    mock_get_all_ngw_units.return_value = all_ngw_units
    mock_get_unit_resource_list.side_effect = get_resource_lists()

    shutdown_routers = ngw_verifier.get_shutdown_resource_list("get-status-routers")
    assert len(shutdown_routers) == router_shutdown_count - 1

    # set router0 back to active
    set_router_status("router0", "ACTIVE")


@mock.patch("juju_verify.verifiers.neutron_gateway.get_unit_resource_list")
@mock.patch("juju_verify.verifiers.neutron_gateway.NeutronGateway.get_all_ngw_units")
@mock.patch("juju_verify.verifiers.neutron_gateway.get_unit_hostname")
def test_get_online_resource_list(mock_get_unit_hostname,
                                  mock_get_all_ngw_units,
                                  mock_get_unit_resource_list):
    """Test validity of resources that will remain online."""
    mock_get_unit_hostname.side_effect = (get_shutdown_host_name_list() +
                                          all_ngw_host_names)
    mock_get_all_ngw_units.return_value = all_ngw_units
    mock_get_unit_resource_list.side_effect = get_resource_lists()

    ngw_verifier = get_ngw_verifier()

    router_online_count = 0
    for host in mock_data:
        if not host["shutdown"]:
            router_online_count += len(host["routers"])

    online_routers = ngw_verifier.get_online_resource_list("get-status-routers")
    assert len(online_routers) == router_online_count

    # test that NOT ACTIVE resources are not being listed as online/available
    set_router_status("router2", "NOTACTIVE")

    mock_get_unit_hostname.side_effect = (get_shutdown_host_name_list() +
                                          all_ngw_host_names)
    mock_get_all_ngw_units.return_value = all_ngw_units
    mock_get_unit_resource_list.side_effect = get_resource_lists()

    online_routers = ngw_verifier.get_online_resource_list("get-status-routers")
    assert len(online_routers) == router_online_count - 1

    # set router2 back to active
    set_router_status("router2", "ACTIVE")


@mock.patch("juju_verify.verifiers.neutron_gateway.get_unit_resource_list")
@mock.patch("juju_verify.verifiers.neutron_gateway.NeutronGateway.get_all_ngw_units")
@mock.patch("juju_verify.verifiers.neutron_gateway.get_unit_hostname")
def test_check_non_redundant_resource(mock_get_unit_hostname,
                                      mock_get_all_ngw_units,
                                      mock_get_unit_resource_list):
    """Test validity of list of resources determined to not be redundant."""
    mock_get_unit_hostname.side_effect = (get_shutdown_host_name_list() +
                                          all_ngw_host_names)
    mock_get_all_ngw_units.return_value = all_ngw_units
    mock_get_unit_resource_list.side_effect = get_resource_lists()

    ngw_verifier = get_ngw_verifier()

    # host0 being shutdown, with no redundancy for its routers (router0, router1)
    result = ngw_verifier.check_non_redundant_resource("get-status-routers")
    assert result.success is False

    mock_get_unit_hostname.side_effect = (get_shutdown_host_name_list() +
                                          all_ngw_host_names)
    mock_get_all_ngw_units.return_value = all_ngw_units
    mock_get_unit_resource_list.side_effect = get_resource_lists()

    ngw_verifier = get_ngw_verifier()

    # add redundancy (but not HA) for router0, router1 onto non-shutdown hosts
    mock_data[1]["routers"].append({"id": "router0", "ha": False, "status": "ACTIVE"})
    mock_data[2]["routers"].append({"id": "router1", "ha": False, "status": "ACTIVE"})
    mock_get_unit_resource_list.side_effect = get_resource_lists()
    result = ngw_verifier.check_non_redundant_resource("get-status-routers")
    assert result.success

    # test setting redundant redundant router0 to NOTACTIVE will result in failure
    mock_data[1]["routers"][-1]["status"] = "NOTACTIVE"
    mock_get_unit_resource_list.side_effect = get_resource_lists()
    result = ngw_verifier.check_non_redundant_resource("get-status-routers")
    assert result.success is False

    # test shutdown host1, which will take down the redundant router0
    mock_data[1]["shutdown"] = True
    mock_get_unit_hostname.side_effect = (get_shutdown_host_name_list() +
                                          all_ngw_host_names)
    mock_get_all_ngw_units.return_value = all_ngw_units
    mock_get_unit_resource_list.side_effect = get_resource_lists()

    ngw_verifier = get_ngw_verifier()
    result = ngw_verifier.check_non_redundant_resource("get-status-routers")
    assert result.success is False

    # reset shutdown for next tests
    mock_data[1]["shutdown"] = False


@mock.patch("juju_verify.verifiers.neutron_gateway.get_unit_resource_list")
@mock.patch("juju_verify.verifiers.neutron_gateway.NeutronGateway.get_all_ngw_units")
@mock.patch("juju_verify.verifiers.neutron_gateway.get_unit_hostname")
def test_warn_router_ha(mock_get_unit_hostname,
                        mock_get_all_ngw_units,
                        mock_get_unit_resource_list):
    """Test existence of warning messages to manually failover HA routers when found."""
    mock_get_unit_hostname.side_effect = (get_shutdown_host_name_list() +
                                          all_ngw_host_names)
    mock_get_all_ngw_units.return_value = all_ngw_units
    mock_get_unit_resource_list.side_effect = get_resource_lists()

    ngw_verifier = get_ngw_verifier()

    result = ngw_verifier.warn_router_ha()
    # no HA to failover, lack of redundancy is detected by check_non_redundant_resource
    assert result.reason == ""

    # Find router0 set it to HA
    for host in mock_data:
        for router in host["routers"]:
            if router["id"] == "router0":
                router["ha"] = True

    mock_get_unit_hostname.side_effect = (get_shutdown_host_name_list() +
                                          all_ngw_host_names)
    mock_get_all_ngw_units.return_value = all_ngw_units
    mock_get_unit_resource_list.side_effect = get_resource_lists()

    ngw_verifier = get_ngw_verifier()

    result = ngw_verifier.warn_router_ha()
    # router is in HA, given instructions to failover
    assert result.reason
