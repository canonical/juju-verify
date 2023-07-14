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
"""Utils unit test suite."""
import os
from typing import Any, Callable, Coroutine, Dict, List
from unittest import mock
from unittest.mock import MagicMock, call

import pytest
from juju.errors import JujuError
from juju.unit import Unit
from pytest import raises

from juju_verify.exceptions import CharmException, VerificationError
from juju_verify.utils.action import cache_manager
from juju_verify.utils.unit import (
    _run_action,
    find_unit_by_hostname,
    find_units,
    find_units_on_machine,
    get_applications_names,
    get_cache_key,
    get_first_active_unit,
    get_related_charm_units_to_app,
    parse_charm_name,
    run_action_on_unit,
    run_action_on_units,
    run_command_on_unit,
    verify_charm_unit,
)


def test_get_cache_key():
    """Test creating key for cache."""
    unit_1 = MagicMock()
    unit_2 = MagicMock()

    assert get_cache_key(unit_1, "test-action") == get_cache_key(unit_1, "test-action")
    assert get_cache_key(unit_1, "test-action") != get_cache_key(unit_1, "action")
    assert get_cache_key(unit_1, "test-action", format="text") != get_cache_key(
        unit_1, "test-action", format="json"
    )
    assert get_cache_key(
        unit_1, "test-action", format="text", test=True
    ) == get_cache_key(unit_1, "test-action", test=True, format="text")
    assert get_cache_key(unit_1, "test-action") != get_cache_key(unit_2, "test-action")


@pytest.mark.asyncio
async def test_run_action():
    """Test running action with cache and wait for results."""

    async def mock_unit_run_action(action: str, **params: Any) -> Coroutine:
        """Mock function for Unit.run_action."""

        async def wait() -> Dict[str, Any]:
            return {"action": action, "params": params, "message": "test"}

        _action = MagicMock()
        _action.wait.side_effect = wait
        return _action

    unit_1 = MagicMock()
    unit_2 = MagicMock()
    unit_1.entity_id.return_value = 1
    unit_2.entity_id.return_value = 2
    cache_manager.enable()  # enable run action cache usage
    unit_1.run_action.side_effect = unit_2.run_action.side_effect = mock_unit_run_action

    # test run_action once
    await _run_action(unit_1, "action", params=dict(format="json"), use_cache=True)

    unit_1.run_action.assert_called_once_with("action", format="json")
    unit_1.run_action.reset_mock()

    # test run_action multiple times without cache
    await _run_action(unit_1, "action-1", params=dict(format="json"), use_cache=False)
    await _run_action(unit_1, "action-2", use_cache=False)
    await _run_action(unit_1, "action-1", params=dict(format="json"), use_cache=False)
    await _run_action(unit_2, "action-1", use_cache=False)

    assert unit_1.run_action.call_count == 3
    unit_1.run_action.assert_has_calls(
        [
            call("action-1", format="json"),
            call("action-2"),
            call("action-1", format="json"),
        ]
    )
    unit_2.run_action.assert_called_once_with("action-1")
    unit_1.run_action.reset_mock()
    unit_2.run_action.reset_mock()

    # test run_action multiple times with cache
    await _run_action(
        unit_1, "action-1", params=dict(format="json"), use_cache=True
    )  # uses cache
    await _run_action(unit_1, "action-2", use_cache=True)  # uses cache
    await _run_action(unit_1, "action-3", use_cache=True)
    await _run_action(unit_1, "action-1", params=dict(format="text"), use_cache=True)
    await _run_action(unit_2, "action-1", use_cache=True)  # uses cache
    await _run_action(unit_2, "action-1", use_cache=True)  # uses cache
    await _run_action(unit_2, "action-2", use_cache=True)

    assert unit_1.run_action.call_count == 2
    unit_1.run_action.assert_has_calls(
        [call("action-3"), call("action-1", format="text")]
    )
    unit_2.run_action.assert_called_once_with("action-2")


@mock.patch("juju_verify.utils.unit._run_action")
def test_run_action_on_units(mock_run_action, model):
    """Test running action on list of units and returning results."""
    # Prepare units and actions data
    action = "unit-action"
    action_params = {"force": True, "debug": False}
    run_on_unit_ids = [f"nova-compute/{i}" for i in [0, 1]]
    run_on_units = [model.units[unit_id] for unit_id in run_on_unit_ids]

    def mock_action_result(status: str) -> Callable:
        async def action_result(unit: Unit, *args, **kwargs):
            # pylint: disable=unused-argument
            _action = MagicMock()
            action_id = run_on_unit_ids.index(unit.entity_id)
            _action.entity_id = f"{action_id}-wait"
            _action.status = status
            return _action

        return action_result

    mock_run_action.side_effect = mock_action_result("completed")

    # create verifier and run actions
    results = run_action_on_units(
        run_on_units, action, use_cache=False, params=action_params
    )

    mock_run_action.assert_has_calls(
        [call(unit, action, action_params, False) for unit in run_on_units]
    )

    assert len(results) == len(run_on_unit_ids)
    assert all(unit_id in results for unit_id in run_on_unit_ids)
    assert all(result.status == "completed" for result in results.values())

    # Raise error if one of the actions failed
    mock_run_action.side_effect = mock_action_result("failed")

    expect_err = os.linesep.join(
        [
            f"Action {action} (ID: {action_result.entity_id}) failed to complete on "
            f"unit {unit_id}. For more info see 'juju show-action-output "
            f"{action_result.entity_id}'"
            for unit_id, action_result in results.items()
        ]
    )

    with raises(VerificationError) as exc:
        run_action_on_units(run_on_units, action, use_cache=False, params=action_params)
        assert str(exc.value) == expect_err


@mock.patch("juju_verify.utils.unit.run_action_on_units")
def test_run_action_on_unit(mock_run_action_on_units, model):
    """Test running action on single unit from the verifier."""
    unit = model.units["nova-compute/0"]
    run_action_on_unit(unit, "test", True)
    mock_run_action_on_units.assert_called_with([unit], "test", True, None)


def test_run_command_on_unit():
    """Test run command on unit."""

    async def mock_run_command(*args, **kwargs):
        return "test output"

    unit = MagicMock()
    unit.run.side_effect = mock_run_command
    cache_manager.enable()

    # run command first time
    result = run_command_on_unit(unit, "test command")
    assert result == "test output"
    unit.run.assert_called_once_with("test command", timeout=2 * 60)
    unit.run.reset_mock()

    # run command second time w/ cache enabled
    result = run_command_on_unit(unit, "test command")
    assert result == "test output"
    unit.run.assert_not_called()
    unit.run.reset_mock()

    # run command third time w/ cache disabled
    result = run_command_on_unit(unit, "test command", use_cache=False)
    assert result == "test output"
    unit.run.assert_called_once_with("test command", timeout=2 * 60)
    unit.run.reset_mock()

    # run command failed
    unit.run.side_effect = JujuError("command failed")
    with pytest.raises(CharmException):
        run_command_on_unit(unit, "test command", use_cache=False)


@pytest.mark.parametrize(
    "charm_url, exp_name",
    [
        ("cs:focal/nova-compute-141", "nova-compute"),
        ("cs:hacluster-74", "hacluster"),
    ],
)
def test_parse_charm_name(charm_url, exp_name):
    """Test function for parsing charm name from charm-ulr."""
    assert parse_charm_name(charm_url) == exp_name


@pytest.mark.parametrize(
    "charm_name, units",
    [
        ("ceph-osd", [("ceph-osd", "ceph-osd/0")]),
        ("ceph-osd", [("ceph-osd", "ceph-osd/0"), ("ceph-osd", "ceph-osd/1")]),
        (
            "ceph-osd",
            [
                ("ceph-osd", "ceph-osd-cluster-1/0"),
                ("ceph-osd", "ceph-osd-cluster-2/0"),
            ],
        ),
    ],
)
def test_verify_charm_unit(charm_name: str, units: List[str]):
    """Test function to verify if units are based on required charm."""
    mock_units = []
    for _charm_name, entity_id in units:
        unit = MagicMock()
        unit.entity_id = entity_id
        unit.charm_url = f"local:focal/{_charm_name}-1"
        mock_units.append(unit)

    verify_charm_unit(charm_name, *mock_units)


@pytest.mark.parametrize(
    "charm_name, units",
    [
        ("ceph-osd", [("ceph-mon", "ceph-mon/0")]),
    ],
)
def test_verify_charm_unit_fail(charm_name: str, units: List[str]):
    """Test function to raise an error if units aren't base on charm."""
    mock_units = []
    for _charm_name, entity_id in units:
        unit = MagicMock()
        unit.entity_id = entity_id
        unit.charm_url = f"local:focal/{_charm_name}-1"
        mock_units.append(unit)

    with pytest.raises(CharmException):
        verify_charm_unit(charm_name, *mock_units)


def test_get_first_active_unit(model):
    """Test function to select first active unit or return None."""
    units = [model.units["ceph-osd/0"], model.units["ceph-osd/1"]]

    # test selecting from two active units
    assert model.units["ceph-osd/0"] == get_first_active_unit(units)

    # test selecting from one active and blocked unit
    model.units["ceph-osd/0"].data["workload-status"]["current"] = "blocked"
    assert model.units["ceph-osd/1"] == get_first_active_unit(units)

    # test selecting from two blocked units
    model.units["ceph-osd/1"].data["workload-status"]["current"] = "blocked"
    assert get_first_active_unit(units) is None

    model.units["ceph-osd/0"].data["workload-status"]["current"] = "active"
    model.units["ceph-osd/1"].data["workload-status"]["current"] = "active"


def test_get_applications_names(model):
    """Test function to get all names of application based on the same charm."""
    ceph_osd_apps = get_applications_names(model, "ceph-osd")
    assert ceph_osd_apps == ["ceph-osd", "ceph-osd-hdd", "ceph-osd-ssd"]


def test_get_related_charm_units_to_app(model):
    """Test function to get all units for the same charm related to application."""
    mock_application = MagicMock()
    mock_ceph_osd_relation = MagicMock()
    mock_ceph_osd_relation.provides.application.charm_url = "cs:focal/ceph-osd-66"
    mock_ceph_osd_relation.provides.application.units = [
        unit
        for unit in model.units.values()
        if parse_charm_name(unit.charm_url) == "ceph-osd"
    ]
    mock_ceph_mon_relation = MagicMock()
    mock_ceph_mon_relation.provides.application.charm_url = "cs:focal/ceph-mon-99"
    mock_ceph_mon_relation.provides.application.units = [
        unit
        for unit in model.units.values()
        if parse_charm_name(unit.charm_url) == "ceph-mon"
    ]
    mock_application.relations = [mock_ceph_osd_relation, mock_ceph_mon_relation]

    units = get_related_charm_units_to_app(mock_application, "ceph-osd")
    assert len(units) == 9
    assert model.units["ceph-osd/0"] in units
    assert model.units["ceph-osd-hdd/0"] in units
    assert model.units["ceph-osd-ssd/0"] in units


@mock.patch("juju_verify.utils.unit.parse_charm_name")
def test_find_unit_by_hostname(mock_parse_charm_name):
    """Test function to find unit by hostname."""
    mock_parse_charm_name.side_effect = lambda charm_url: charm_url
    mock_model = MagicMock()
    mock_model.units = {}
    for charm in ["ceph-osd", "ceph-mon"]:
        for i in range(3):
            mock_unit = MagicMock()
            mock_unit.charm_url = charm
            mock_unit.machine.hostname = (
                f"host.{i}"  # ceph-mon units are on same machine
            )
            mock_model.units[f"{charm}/{i}"] = mock_unit

    # find ceph-osd unit
    unit = find_unit_by_hostname(mock_model, "host.0", "ceph-osd")
    assert unit.charm_url == "ceph-osd"
    assert unit.machine.hostname == "host.0"

    # try to find unknown hostname
    with pytest.raises(CharmException):
        find_unit_by_hostname(mock_model, "host.99", "ceph-osd")

    # try to find unknown charm
    with pytest.raises(CharmException):
        find_unit_by_hostname(mock_model, "host.0", "ceph-osd-test")


@pytest.mark.asyncio
async def test_find_units(model, all_units):
    """Test that find_units returns correct list of Unit objects."""
    unit_list = await find_units(model, all_units)

    assert len(unit_list) == len(all_units)

    result = zip(all_units, unit_list)
    for unit_name, unit_obj in result:
        assert isinstance(unit_obj, Unit)
        assert unit_obj.entity_id == unit_name

    # fail if requested unit is not in the list of all units

    missing_unit = "foo/0"
    expected_message = f"Unit '{missing_unit}' not found in the model."

    with pytest.raises(CharmException) as error:
        await find_units(model, [missing_unit])
        assert expected_message in str(error.value)


@pytest.mark.asyncio
async def test_find_units_on_machine(model, all_units):
    """Test that find_units_on_machine function returns correct units."""
    machine_1_name = "0"
    machine_2_name = "1"

    machine_1 = MagicMock()
    machine_1.entity_id = machine_1_name
    machine_2 = MagicMock()
    machine_2.entity_id = machine_2_name

    machine_1_units = all_units[:3]
    machine_2_units = all_units[3:]

    for unit_name, unit in model.units.items():
        if unit_name in machine_1_units:
            unit.machine = machine_1
        elif unit_name in machine_2_units:
            unit.machine = machine_2

    found_units = await find_units_on_machine(model, [machine_1_name])

    assert machine_1_units == [unit.entity_id for unit in found_units]
