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
import asyncio
from typing import List
from unittest.mock import MagicMock, call, patch

import pytest
from juju.action import Action
from juju.unit import Unit
from pytest import raises

from juju_verify.exceptions import VerificationError, CharmException
from juju_verify.utils.unit import (
    run_action_on_units,
    verify_charm_unit,
    parse_charm_name,
    get_first_active_unit,
    get_applications_names, run_action_on_unit
)


def test_run_action_on_units(mocker, model, all_units):
    """Test running action on list of units and returning results."""
    # Mock async lib calls
    loop = MagicMock()
    mocker.patch.object(asyncio, 'get_event_loop').return_value = loop
    mocker.patch.object(asyncio, 'gather')

    # Prepare units and actions data
    action = 'unit-action'
    action_params = {'force': True, 'debug': False}
    juju_actions = []
    juju_actions_wait = []
    run_on_unit_ids = all_units[:2]
    run_on_units = [model.units[unit_id] for unit_id in run_on_unit_ids]

    # Prepare mocks of juju actions.
    # In the live code, we need to run/await each action twice. First call
    # creates an action on the controller (Unit.run_action()) and the second
    # call waits for action result (Action.wait()). These two sets of calls
    # are mocked as two lists of Action objects 'juju_actions' and
    # juju_actions_wait'.
    for i, unit in enumerate(run_on_units):
        juju_action = Action(str(i), model)
        juju_action_wait = Action(str(i) + '-wait', model)
        juju_action_wait.status = 'completed'

        juju_actions.append(juju_action)
        juju_actions_wait.append(juju_action_wait)

    Unit.run_action.side_effect = juju_actions
    Action.wait.side_effect = juju_actions_wait

    loop.run_until_complete.return_value = juju_actions_wait
    asyncio.gather.side_effect = [juju_actions, juju_actions_wait]

    # create verifier and run actions
    results = run_action_on_units(run_on_units, action, **action_params)

    for unit in run_on_units:
        unit.run_action.assert_called_with(action, **action_params)

    expected_gather_calls = [
        call(*juju_actions),
        call(*juju_actions_wait)
    ]

    expected_run_loop_calls = [
        call(juju_actions),
        call(juju_actions_wait),
    ]

    asyncio.gather.assert_has_calls(expected_gather_calls)
    loop.run_until_complete.assert_has_calls(expected_run_loop_calls)

    assert results == dict(zip(run_on_unit_ids, juju_actions_wait))

    # Raise error if one of the actions failed
    failed_action = juju_actions_wait[0]
    failed_action.status = 'failed'
    failed_unit = run_on_unit_ids[0]

    expect_err = 'Action {0} (ID: {1}) failed to complete on unit {2}. For ' \
                 'more info see "juju show-action-output {1}"' \
                 ''.format(action, failed_action.entity_id, failed_unit)

    Unit.run_action.side_effect = juju_actions
    Action.wait.side_effect = juju_actions_wait
    asyncio.gather.side_effect = [juju_actions, juju_actions_wait]

    with raises(VerificationError) as exc:
        run_action_on_units(run_on_units, action, **action_params)

    assert str(exc.value) == expect_err


@patch("juju_verify.utils.unit.run_action_on_units")
def test_base_verifier_run_action_on_unit(mock_run_action_on_units, model):
    """Test running action on single unit from the verifier."""
    unit = model.units["nova-compute/0"]
    run_action_on_unit(unit, "test")
    mock_run_action_on_units.assert_called_with([unit], "test")


@pytest.mark.parametrize("charm_url, exp_name", [
    ("cs:focal/nova-compute-141", "nova-compute"),
    ("cs:hacluster-74", "hacluster"),
])
def test_parse_charm_name(charm_url, exp_name):
    """Test function for parsing charm name from charm-ulr."""
    assert parse_charm_name(charm_url) == exp_name


@pytest.mark.parametrize("charm_name, units", [
    ("ceph-osd", [("ceph-osd", "ceph-osd/0")]),
    ("ceph-osd", [("ceph-osd", "ceph-osd/0"), ("ceph-osd", "ceph-osd/1")]),
    ("ceph-osd", [("ceph-osd", "ceph-osd-cluster-1/0"),
                  ("ceph-osd", "ceph-osd-cluster-2/0")]),
])
def test_verify_charm_unit(charm_name: str, units: List[str]):
    """Test function to verify if units are based on required charm."""
    mock_units = []
    for _charm_name, entity_id in units:
        unit = MagicMock()
        unit.entity_id = entity_id
        unit.charm_url = f"local:focal/{_charm_name}-1"
        mock_units.append(unit)

    verify_charm_unit(charm_name, *mock_units)


@pytest.mark.parametrize("charm_name, units", [
    ("ceph-osd", [("ceph-mon", "ceph-mon/0")]),
])
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
