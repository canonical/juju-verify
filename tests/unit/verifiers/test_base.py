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
"""Base class test suite."""

import asyncio
from unittest.mock import ANY, MagicMock, PropertyMock, call

import pytest
from juju.action import Action
from juju.model import Model
from juju.unit import Unit

from juju_verify.exceptions import VerificationError
from juju_verify.verifiers.base import BaseVerifier, Result, logger


@pytest.mark.parametrize('success, reason',
                         [(True, 'Congratulation'),
                          (True, ''),
                          (False, 'FailReason')])
def test_result_formatting(success, reason):
    """Test expected format of the Result.format()."""
    result = Result(success, reason)
    common_str = 'Result: '
    success_str = 'OK' if success else 'FAIL'
    reason_str = '\nReason: {}'.format(reason) if reason else ''

    expected_msg = common_str + success_str + reason_str
    assert str(result) == expected_msg


@pytest.mark.parametrize('result_1, result_2, expect_result',
                         [(Result(True, 'foo'), Result(True, 'bar'),
                           Result(True, 'foo\nbar')),
                          (Result(True, ''), Result(False, 'foo'),
                           Result(False, 'foo')),
                          (Result(False, 'foo'), Result(True, ''),
                           Result(False, 'foo')),
                          (Result(False, 'foo\n'), Result(False, 'bar'),
                           Result(False, 'foo\nbar'))])
def test_result_add(result_1, result_2, expect_result):
    """Test '+' operator on Result objects."""
    result = result_1 + result_2

    assert result.success == expect_result.success
    assert result.reason == expect_result.reason


def test_result_add_raises_not_implemented():
    """Test that '+' operator raises error if both operands aren't Result."""
    with pytest.raises(NotImplementedError):
        _ = Result(True) + False


def test_base_verifier_verify_no_units():
    """Function 'verify' should fail if verifier has not units."""
    expected_msg = 'Can not run verification. This verifier ' \
                   'is not associated with any units.'

    with pytest.raises(VerificationError) as exc:
        BaseVerifier([])

    assert str(exc.value) == expected_msg


def test_base_verifier_multiple_models():
    """Fail if verifier is initiated with untis from different models."""
    model_1 = Model()
    model_2 = Model()

    unit_1 = Unit('nova-compute/0', model_1)
    unit_2 = Unit('nova-compute/1', model_2)

    with pytest.raises(VerificationError) as exc:
        BaseVerifier([unit_1, unit_2])

    assert str(exc.value) == 'Verifier initiated with units from multiple ' \
                             'models.'


def test_base_verifier_warn_on_unchecked_units(mocker):
    """Log warning if principal unit is not checked on affected machine."""
    machine = MagicMock()
    machine.entity_id = '0'

    unit_data = {'subordinate': False}

    mocker.patch.object(Unit, 'machine',
                        new_callable=PropertyMock(return_value=machine))
    mocker.patch.object(Unit, 'data',
                        new_callable=PropertyMock(return_value=unit_data))
    mocker.patch.object(Model, 'units')
    log_warning = mocker.patch.object(logger, 'warning')

    model = Model()
    checked_unit = Unit('nova-compute/0', model)
    unchecked_unit = Unit('ceph_osd/0', model)
    model.units = {'nova-compute/0': checked_unit,
                   'ceph-osd/0': unchecked_unit}

    expected_msg = 'Machine %s runs other principal unit that is not being ' \
                   'checked: %s'

    verifier = BaseVerifier([checked_unit])

    with pytest.raises(NotImplementedError):
        verifier.verify('shutdown')

    log_warning.assert_called_with(expected_msg,
                                   machine.entity_id,
                                   unchecked_unit.entity_id)
    # Test run without warning
    log_warning.reset_mock()
    verifier = BaseVerifier([checked_unit, unchecked_unit])

    with pytest.raises(NotImplementedError):
        verifier.verify('shutdown')

    log_warning.assert_not_called()


def test_base_verifier_unit_ids():
    """Test return value of property BaseVerifier.unit_ids."""
    unit_ids = ['nova-compute/0', 'nova-compute/1']
    units = []
    model = Model()

    for unit_id in unit_ids:
        units.append(Unit(unit_id, model))

    verifier = BaseVerifier(units)

    assert unit_ids == verifier.unit_ids


@pytest.mark.parametrize('check_name, check_method',
                         [('shutdown', 'verify_shutdown'),
                          ('reboot', 'verify_reboot')])
def test_base_verifier_supported_checks(mocker, check_name, check_method):
    """Test that each supported check executes expected method."""
    unit = Unit('foo', Model())
    mock_method = mocker.patch.object(BaseVerifier, check_method)

    verifier = BaseVerifier([unit])

    verifier.verify(check_name)
    mock_method.assert_called_once()


def test_base_verifier_unsupported_check():
    """Raise exception if check is unknown/unsupported."""
    unit = Unit('foo', Model())
    bad_check = 'bar'
    expected_msg = 'Unsupported verification check "{}" for charm ' \
                   '{}'.format(bad_check, BaseVerifier.NAME)

    verifier = BaseVerifier([unit])

    with pytest.raises(NotImplementedError) as exc:
        verifier.verify(bad_check)

    assert str(exc.value) == expected_msg


def test_base_verifier_not_implemented_checks():
    """Test that all checks raise NotImplemented in BaseVerifier."""
    unit = Unit('foo', Model())
    verifier = BaseVerifier([unit])

    for check in BaseVerifier.supported_checks():
        with pytest.raises(NotImplementedError):
            verifier.verify(check)


def test_base_verifier_unexpected_verify_error(mocker):
    """Test 'verify' raises VerificationError if case of unexpected failure."""
    unit = Unit('foo', Model())
    verifier = BaseVerifier([unit])
    check = BaseVerifier.supported_checks()[0]
    check_method = BaseVerifier._action_map().get(check).__name__
    internal_msg = 'Something failed.'
    internal_err = RuntimeError(internal_msg)
    expected_msg = 'Verification failed: {}'.format(internal_msg)
    mocker.patch.object(BaseVerifier, check_method).side_effect = internal_err

    with pytest.raises(VerificationError) as exc:
        verifier.verify(check)

    assert str(exc.value) == expected_msg


def test_base_verifier_unit_from_id():
    """Test finding units in verifier by their IDs."""
    present_unit = 'compute/0'
    missing_unit = 'compute/1'
    expected_msg = 'Unit {} was not found in {} ' \
                   'verifier.'.format(missing_unit, BaseVerifier.NAME)
    unit = Unit(present_unit, Model())
    verifier = BaseVerifier([unit])

    found_unit = verifier.unit_from_id(present_unit)

    assert found_unit == unit

    # raise error when querying non-existent unit

    with pytest.raises(VerificationError) as exc:
        verifier.unit_from_id(missing_unit)

    assert str(exc.value) == expected_msg


def test_base_verifier_data_from_action(mocker):
    """Test helper function that parses data from Action.data.results dict."""
    host_key = 'host'
    host_value = 'compute.0'
    data = {'results': {host_key: host_value}}
    default = 'default'

    mocker.patch.object(Action, 'data',
                        new_callable=PropertyMock(return_value=data))
    action = Action('0', Model())

    output = BaseVerifier.data_from_action(action, host_key, default)
    assert output == host_value

    # return default on missing key

    output = BaseVerifier.data_from_action(action, 'foo', default)
    assert output == default


def test_base_verifier_run_action_on_units(mocker, model, all_units):
    """Test running action on list of units and returning results."""
    # Mock async lib calls
    loop = MagicMock()
    mocker.patch.object(asyncio, 'get_event_loop').return_value = loop
    mocker.patch.object(asyncio, 'gather')

    # Put spy on unit_id resolution
    id_to_unit = mocker.spy(BaseVerifier, 'unit_from_id')

    # Prepare units and actions data
    action = 'unit-action'
    action_params = {'force': True, 'debug': False}
    juju_actions = []
    juju_actions_wait = []
    run_on_unit_ids = all_units[:2]
    run_on_units = [model.units[unit] for unit in run_on_unit_ids]

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
    verifier = BaseVerifier(run_on_units)
    results = verifier.run_action_on_units(run_on_unit_ids, action,
                                           **action_params)

    # verify results and expected calls
    id_to_unit.assert_has_calls([call(verifier, id_) for id_
                                 in run_on_unit_ids])

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

    with pytest.raises(VerificationError) as exc:
        verifier.run_action_on_units(run_on_unit_ids, action, **action_params)
    assert str(exc.value) == expect_err


def test_base_verifier_run_action_on_unit(mocker):
    """Test running action on single unit from the verifier."""
    unit_name = 'nova-compute/0'
    action = 'unit-action'
    action_params = {'force': True, 'debug': False}
    action_result = Action('0', Model())
    mocker.patch.object(BaseVerifier, 'run_action_on_units'
                        ).return_value = {unit_name: action_result}

    unit = Unit(unit_name, Model())

    verifier = BaseVerifier([unit])
    result = verifier.run_action_on_unit(unit_name, action, **action_params)

    verifier.run_action_on_units.assert_called_with([unit_name],
                                                    action,
                                                    **action_params)
    assert result == action_result


def test_base_verifier_run_action_on_all_units(mocker):
    """Test running action on all units in verifier."""
    model = Model()
    action = 'unit-action'
    action_params = {'force': True, 'debug': False}
    unit_names = ['nova_compute/0', 'nova-compute/1']
    result_map = {unit: Action('0', model) for unit in unit_names}
    units = [Unit(name, model) for name in unit_names]

    mocker.patch.object(BaseVerifier, 'run_action_on_units'
                        ).return_value = result_map

    verifier = BaseVerifier(units)
    result = verifier.run_action_on_all(action, **action_params)

    verifier.run_action_on_units.assert_called_with(unit_names,
                                                    action,
                                                    **action_params)

    assert result == result_map


@pytest.mark.parametrize('result_list',
                         [([Result(False)]),
                          ([Result(True), Result(True)]),
                          ([Result(True), Result(False), Result(True)])
                          ])
def test_base_verifier_aggregate_results(mocker, result_list):
    """Test helper method that aggregates Result instances."""
    spy_on_add = mocker.spy(Result, '__add__')
    expected_calls = [call(ANY, result) for result in result_list[1:]]
    expected_result = all(result.success for result in result_list)

    final_result = BaseVerifier.aggregate_results(*result_list)

    spy_on_add.assert_has_calls(expected_calls)
    assert isinstance(final_result, Result)
    assert final_result.success == expected_result
