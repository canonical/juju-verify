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
import json
from copy import deepcopy
from itertools import cycle, permutations
from unittest import mock
from unittest.mock import MagicMock

from juju.unit import Unit
import pytest

from juju_verify.verifiers import NeutronGateway, Result, Severity

all_ngw_units = []
for i in range(3):
    ngw = MagicMock()
    machine = MagicMock()
    machine.hostname = f"host{i}"
    ngw.entity_id = f"neutron-gateway/{i}"
    ngw.machine = machine
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

all_ngw_host_names = [host["host"] for host in mock_data]

model = MagicMock()


def get_ngw_verifier():
    """Get new NeutronGateway verifier (used for applying changes in shutdown list)."""
    units = []
    for mock_unit in mock_data:
        if mock_unit["shutdown"]:
            unit = Unit(mock_unit["unit"], model)
            machine = MagicMock()
            machine.hostname = mock_unit["host"]
            unit.machine = machine
            units.append(unit)
    return NeutronGateway(units)


def get_resource_lists():
    """Get all routers in mock data."""
    return [host["routers"] for host in mock_data]


def get_shutdown_host_name_list():
    """Get all hostnames of all hosts being shutdown."""
    return [host["host"] for host in mock_data if host["shutdown"]]


def set_router_status(routerid, status):
    """Set status of given router id in mock data."""
    for host in mock_data:
        for router in host["routers"]:
            if router["id"] == routerid:
                router["status"] = status


@mock.patch("juju_verify.verifiers.neutron_gateway.NeutronGateway.get_unit_resource_list")  # noqa: E501 pylint: disable=C0301
@mock.patch("juju_verify.verifiers.neutron_gateway.NeutronGateway.get_all_ngw_units")
def test_get_resource_list(mock_get_all_ngw_units,
                           mock_get_unit_resource_list):
    """Test list of resources returned by get_resource_list."""
    mock_get_all_ngw_units.return_value = all_ngw_units
    mock_get_unit_resource_list.side_effect = get_resource_lists()

    ngw_verifier = get_ngw_verifier()
    router_list = ngw_verifier.get_resource_list("get-status-routers")

    router_count = 0
    for host in mock_data:
        router_count += len(host["routers"])
    assert len(router_list) == router_count


@mock.patch("juju_verify.verifiers.neutron_gateway.NeutronGateway.get_unit_resource_list")  # noqa: E501 pylint: disable=C0301
@mock.patch("juju_verify.verifiers.neutron_gateway.NeutronGateway.get_all_ngw_units")
def test_get_shutdown_resource_list(mock_get_all_ngw_units,
                                    mock_get_unit_resource_list):
    """Test validity of list of resources to be shutdown."""
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

    mock_get_all_ngw_units.return_value = all_ngw_units
    mock_get_unit_resource_list.side_effect = get_resource_lists()

    shutdown_routers = ngw_verifier.get_shutdown_resource_list("get-status-routers")
    assert len(shutdown_routers) == router_shutdown_count - 1

    # set router0 back to active
    set_router_status("router0", "ACTIVE")


@mock.patch("juju_verify.verifiers.neutron_gateway.NeutronGateway.get_unit_resource_list")  # noqa: E501 pylint: disable=C0301
@mock.patch("juju_verify.verifiers.neutron_gateway.NeutronGateway.get_all_ngw_units")
def test_get_online_resource_list(mock_get_all_ngw_units,
                                  mock_get_unit_resource_list):
    """Test validity of resources that will remain online."""
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

    mock_get_all_ngw_units.return_value = all_ngw_units
    mock_get_unit_resource_list.side_effect = get_resource_lists()

    online_routers = ngw_verifier.get_online_resource_list("get-status-routers")
    assert len(online_routers) == router_online_count - 1

    # set router2 back to active
    set_router_status("router2", "ACTIVE")


@mock.patch("juju_verify.verifiers.neutron_gateway.NeutronGateway.get_unit_resource_list")  # noqa: E501 pylint: disable=C0301
@mock.patch("juju_verify.verifiers.neutron_gateway.NeutronGateway.get_all_ngw_units")
def test_check_non_redundant_resource(mock_get_all_ngw_units,
                                      mock_get_unit_resource_list):
    """Test validity of list of resources determined to not be redundant."""
    mock_get_all_ngw_units.return_value = all_ngw_units
    mock_get_unit_resource_list.side_effect = cycle(get_resource_lists())

    ngw_verifier = get_ngw_verifier()

    # host0 being shutdown, with no redundancy for its routers (router0, router1)
    result = ngw_verifier.check_non_redundant_resource("get-status-routers")
    assert result.success is False

    mock_get_all_ngw_units.return_value = all_ngw_units
    mock_get_unit_resource_list.side_effect = cycle(get_resource_lists())

    ngw_verifier = get_ngw_verifier()

    # store original mock_data
    global mock_data
    original_mock = deepcopy(mock_data)
    # add redundancy (but not HA) for router0, router1 onto non-shutdown hosts
    mock_data[1]["routers"].append({"id": "router0", "ha": False, "status": "ACTIVE"})
    mock_data[2]["routers"].append({"id": "router1", "ha": False, "status": "ACTIVE"})
    mock_get_unit_resource_list.side_effect = cycle(get_resource_lists())
    result = ngw_verifier.check_non_redundant_resource("get-status-routers")
    assert result.success

    # test setting redundant redundant router0 to NOTACTIVE will result in failure
    mock_data[1]["routers"][-1]["status"] = "NOTACTIVE"
    mock_get_unit_resource_list.side_effect = cycle(get_resource_lists())
    result = ngw_verifier.check_non_redundant_resource("get-status-routers")
    assert result.success is False

    # test shutdown host1, which will take down the redundant router0
    mock_data[1]["shutdown"] = True
    mock_get_all_ngw_units.return_value = all_ngw_units
    mock_get_unit_resource_list.side_effect = cycle(get_resource_lists())

    ngw_verifier = get_ngw_verifier()
    result = ngw_verifier.check_non_redundant_resource("get-status-routers")
    assert result.success is False

    # restore mock_data
    mock_data = original_mock


@mock.patch("juju_verify.verifiers.neutron_gateway.NeutronGateway.get_unit_resource_list")  # noqa: E501 pylint: disable=C0301
@mock.patch("juju_verify.verifiers.neutron_gateway.NeutronGateway.get_all_ngw_units")
def test_warn_router_ha(mock_get_all_ngw_units,
                        mock_get_unit_resource_list):
    """Test existence of warning messages to manually failover HA routers when found."""
    mock_get_all_ngw_units.return_value = all_ngw_units
    mock_get_unit_resource_list.side_effect = get_resource_lists()

    ngw_verifier = get_ngw_verifier()

    result = ngw_verifier.warn_router_ha()
    # no HA to failover, lack of redundancy is detected by check_non_redundant_resource
    assert result == Result()

    # Find router0 set it to HA
    expected_router = None
    expected_unit = None
    expected_host = None
    for host in mock_data:
        for router in host["routers"]:
            if router["id"] == "router0":
                router["ha"] = True
                expected_router = router["id"]
                expected_unit = host["unit"].entity_id
                expected_host = host["host"]

    mock_get_all_ngw_units.return_value = all_ngw_units
    mock_get_unit_resource_list.side_effect = get_resource_lists()

    ngw_verifier = get_ngw_verifier()

    result = ngw_verifier.warn_router_ha()

    router_format = f'{expected_router} (on {expected_unit}, hostname: {expected_host})'
    expected_message = ("It's recommended that you manually failover the following "
                        "routers: {}".format(router_format))
    expected_result = Result(Severity.WARN, expected_message)
    # router is in HA, given instructions to failover
    assert result.partials == expected_result.partials


@mock.patch("juju_verify.verifiers.neutron_gateway.NeutronGateway.version_check")
@mock.patch("juju_verify.verifiers.neutron_gateway.NeutronGateway.check_non_redundant_resource")  # noqa: E501 pylint: disable=C0301
@mock.patch("juju_verify.verifiers.neutron_gateway.NeutronGateway.warn_lbaas_present")
@mock.patch("juju_verify.verifiers.neutron_gateway.NeutronGateway.warn_router_ha")
def test_verify_reboot_shutdown(mock_warn_router_ha,
                                mock_warn_lbaas_preent,
                                mock_check_non_redundant_resource,
                                mock_version_check):
    """Test that reboot/shutdown call appropriate checks."""
    ngw_verifier = get_ngw_verifier()
    ngw_verifier.verify_reboot()
    assert mock_check_non_redundant_resource.call_count == 2
    mock_version_check.assert_called_once()
    mock_warn_router_ha.assert_called_once()
    mock_warn_lbaas_preent.assert_called_once()

    mock_check_non_redundant_resource.reset_mock()
    mock_version_check.reset_mock()
    mock_warn_router_ha.reset_mock()
    mock_warn_lbaas_preent.reset_mock()

    ngw_verifier.verify_shutdown()
    mock_version_check.assert_called_once()
    mock_warn_router_ha.assert_called_once()
    assert mock_check_non_redundant_resource.call_count == 2


@mock.patch("juju_verify.verifiers.neutron_gateway.run_action_on_unit")
@mock.patch("juju_verify.verifiers.neutron_gateway.data_from_action")
def test_get_unit_resource_list(mock_data_from_action, mock_run_action_on_unit):
    """Test Neutron agent resources are retrieved via Juju actions."""
    resource = {"routers": [{"id": "r1"}]}
    mock_data_from_action.return_value = json.dumps(resource)
    resource_list = NeutronGateway.get_unit_resource_list(all_ngw_units[0],
                                                          "get-status-routers")
    mock_run_action_on_unit.assert_called_once()
    assert resource == resource_list


def test_get_all_gw_units(model):
    """Test that `get_all_gw_units` returns also units taht are not being verified."""
    ngw_unit_0 = model.units.get('neutron-gateway/0')
    ngw_unit_1 = model.units.get('neutron-gateway/1')

    verify_units = [ngw_unit_0]
    expect_units = [ngw_unit_0, ngw_unit_1]
    verifier = NeutronGateway(verify_units)

    assert verifier.get_all_ngw_units() == expect_units


@pytest.mark.parametrize('units_with_lbaas, checked_units', [
    ({'neutron-gateway/0'}, {'neutron-gatewy/0'}),
    ({'neutron-gateway/0', 'neutron-gateway/1'}, {'neutron-gateway/1'}),
    ({'neutron-gateway/0', 'neutron-gateway/1'}, {'neutron-gateway/0',
                                                  'neutron-gateway/1'}),
    (set(), {'neutron-gateway/0'}),
])
def test_warn_lbaas_present_pass(mocker, model, units_with_lbaas, checked_units):
    """Check that `warn_lbaas_present` method returns expected results."""
    mock_get_resource_list = mocker.patch.object(NeutronGateway, 'get_resource_list')
    resource_list = []
    for unit in units_with_lbaas:
        resource_list.append({'juju-entity-id': unit})
    mock_get_resource_list.return_value = resource_list

    affected_units: set = checked_units & units_with_lbaas

    units = [Unit(unit, model) for unit in checked_units]
    verifier = NeutronGateway(units)
    result = verifier.warn_lbaas_present()

    if affected_units:
        message = ('Following units have neutron LBaasV2 load-balancers that will be'
                   ' lost on unit shutdown: {}')
        expected_results = []
        # Note (martin-kalcok): Since the order of the affected units in the resulting
        #                       message is not guaranteed, We need to create permutations
        #                       of all possible options and check if our result is in
        #                       there.
        for permutation in permutations(affected_units):
            reason = message.format(", ".join(permutation))
            expected_results.append(Result(Severity.WARN, reason))
        assert result in expected_results
    else:
        assert result == Result()


@mock.patch("juju_verify.verifiers.neutron_gateway.NeutronGateway.check_minimum_version")
@mock.patch("juju_verify.verifiers.neutron_gateway.NeutronGateway.check_non_redundant_resource")  # noqa: E501 pylint: disable=C0301
@mock.patch("juju_verify.verifiers.neutron_gateway.NeutronGateway.warn_lbaas_present")
@mock.patch("juju_verify.verifiers.neutron_gateway.NeutronGateway.warn_router_ha")
def test_too_old_juju_version(mock_warn_router_ha,
                              mock_warn_lbaas_preent,
                              mock_check_non_redundant_resource,
                              mock_version_check):
    """Test that insufficient juju version stops check execution."""
    failed_version_check = Result(Severity.FAIL, 'Juju version too low.')
    mock_version_check.return_value = failed_version_check
    verifier = get_ngw_verifier()

    result = verifier.verify_shutdown()

    assert result == failed_version_check
    mock_version_check.assert_called_once()
    mock_warn_router_ha.assert_not_called()
    mock_warn_lbaas_preent.assert_not_called()
    mock_check_non_redundant_resource.assert_not_called()
