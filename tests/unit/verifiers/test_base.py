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
from unittest import mock
from unittest.mock import MagicMock, PropertyMock

import pytest
from juju.model import Model
from juju.unit import Unit

from juju_verify.exceptions import VerificationError
from juju_verify.verifiers.base import BaseVerifier
from juju_verify.verifiers.result import Partial, Severity


def test_base_verifier_verify_no_units():
    """Function 'verify' should fail if verifier has not units."""
    expected_msg = (
        "Can not run verification. This verifier is not associated with any units."
    )

    with pytest.raises(VerificationError) as exc:
        BaseVerifier([])

    assert str(exc.value) == expected_msg


def test_base_verifier_multiple_models():
    """Fail if verifier is initiated with untis from different models."""
    model_1 = Model()
    model_2 = Model()

    unit_1 = Unit("nova-compute/0", model_1)
    unit_2 = Unit("nova-compute/1", model_2)

    with pytest.raises(VerificationError) as exc:
        BaseVerifier([unit_1, unit_2])

    assert str(exc.value) == "Verifier initiated with units from multiple models."


def test_base_verifier_warn_on_unchecked_units(mocker):
    """Log warning if principal unit is not checked on affected machine."""
    machine = MagicMock()
    machine.entity_id = "0"

    unit_data = {"subordinate": False}

    mocker.patch.object(
        Unit, "machine", new_callable=PropertyMock(return_value=machine)
    )
    mocker.patch.object(Unit, "data", new_callable=PropertyMock(return_value=unit_data))
    mocker.patch.object(Model, "units")

    model = Model()
    checked_unit = Unit("nova-compute/0", model)
    unchecked_unit = Unit("ceph_osd/0", model)
    model.units = {"nova-compute/0": checked_unit, "ceph-osd/0": unchecked_unit}

    expected_partial_result = Partial(
        Severity.WARN,
        f"Machine {machine.entity_id} runs other "
        f"principal unit that is not being checked:"
        f" {unchecked_unit.entity_id}",
    )

    verifier = BaseVerifier([checked_unit])

    result = verifier.check_affected_machines()

    assert expected_partial_result in result.partials

    # Test run without warning
    verifier = BaseVerifier([checked_unit, unchecked_unit])

    result = verifier.check_affected_machines()

    assert expected_partial_result not in result.partials

    # Test run excluding missing unit explicitly
    verifier = BaseVerifier(
        units=[checked_unit], exclude_affected_units=[unchecked_unit]
    )

    result = verifier.check_affected_machines()

    assert expected_partial_result not in result.partials


def test_base_verifier_unit_ids():
    """Test return value of property BaseVerifier.unit_ids."""
    unit_ids = ["nova-compute/0", "nova-compute/1"]
    units = []
    model = Model()

    for unit_id in unit_ids:
        units.append(Unit(unit_id, model))

    verifier = BaseVerifier(units)

    assert unit_ids == verifier.unit_ids


@pytest.mark.parametrize(
    "check_name, check_method",
    [("shutdown", "verify_shutdown"), ("reboot", "verify_reboot")],
)
def test_base_verifier_supported_checks(mocker, check_name, check_method):
    """Test that each supported check executes expected method."""
    unit = Unit("foo", Model())
    mocker.patch.object(BaseVerifier, "check_has_sub_machines")
    mock_method = mocker.patch.object(BaseVerifier, check_method)

    verifier = BaseVerifier([unit])

    verifier.verify(check_name)
    mock_method.assert_called_once()


def test_base_verifier_unsupported_check(mocker):
    """Raise exception if check is unknown/unsupported."""
    unit = Unit("foo", Model())
    bad_check = "bar"
    expected_msg = (
        f"Unsupported verification check '{bad_check}' for charm "
        f"{BaseVerifier.NAME}"
    )
    mocker.patch.object(BaseVerifier, "check_has_sub_machines")
    verifier = BaseVerifier([unit])

    with pytest.raises(NotImplementedError) as exc:
        verifier.verify(bad_check)

    assert str(exc.value) == expected_msg


def test_base_verifier_not_implemented_checks(mocker):
    """Test that all checks raise NotImplemented in BaseVerifier."""
    unit = Unit("foo", Model())
    mocker.patch.object(BaseVerifier, "check_has_sub_machines")
    verifier = BaseVerifier([unit])

    for check in BaseVerifier.supported_checks():
        with pytest.raises(NotImplementedError):
            verifier.verify(check)


def test_base_verifier_unexpected_verify_error(mocker):
    """Test 'verify' raises VerificationError if case of unexpected failure."""
    unit = Unit("foo", Model())
    mocker.patch.object(BaseVerifier, "check_has_sub_machines")
    verifier = BaseVerifier([unit])
    check = BaseVerifier.supported_checks()[0]
    check_method = BaseVerifier._action_map().get(check).__name__
    internal_msg = "Something failed."
    internal_err = RuntimeError(internal_msg)
    expected_msg = f"Verification failed: {internal_msg}"
    mocker.patch.object(BaseVerifier, check_method).side_effect = internal_err

    with pytest.raises(VerificationError) as exc:
        verifier.verify(check)

    assert str(exc.value) == expected_msg


def test_base_verifier_unit_from_id():
    """Test finding units in verifier by their IDs."""
    present_unit = "compute/0"
    missing_unit = "compute/1"
    expected_msg = f"Unit {missing_unit} was not found in {BaseVerifier.NAME} verifier."
    unit = Unit(present_unit, Model())
    verifier = BaseVerifier([unit])

    found_unit = verifier.unit_from_id(present_unit)

    assert found_unit == unit

    # raise error when querying non-existent unit

    with pytest.raises(VerificationError) as exc:
        verifier.unit_from_id(missing_unit)

    assert str(exc.value) == expected_msg


@mock.patch("juju_verify.verifiers.base.run_action_on_units")
def test_base_verifier_run_action_on_all_units(mock_run_action_on_units, model):
    """Test running action on all units in verifier."""
    units = list(model.units.values())
    verifier = BaseVerifier(units)
    verifier.run_action_on_all("test", use_cache=False)

    mock_run_action_on_units.assert_called_with(units, "test", False, None)


def test_base_verifier_check_has_sub_machines(mocker):
    """Test check unit has sub machines verifier."""
    main_unit = "nova-compute/0"
    child_unit = "child-unit/0"
    # Mock async lib calls
    loop = MagicMock()
    mocker.patch.object(asyncio, "get_event_loop").return_value = loop

    # Generic mock for all units
    model = Model()
    unit_data = {"subordinate": False}
    mocker.patch.object(Unit, "data", new_callable=PropertyMock(return_value=unit_data))

    # dict of units/machines to test with
    mocker.patch.object(Model, "units")
    units = [
        {"name": main_unit, "machine": "0", "leader": True},
        {"name": child_unit, "machine": "0/lxd/0", "leader": True},
    ]

    # is_leader_from_status result for every child
    mocker.patch.object(loop, "run_until_complete").return_value = [True]

    unit_list = []
    for unit in units:
        unit["unit_object"] = Unit(unit["name"], model)
        unit_list.append((unit["name"], unit["unit_object"]))
        mocker.patch.object(
            unit["unit_object"],
            "machine",
            new_callable=PropertyMock(return_value=MagicMock()),
        )
        mocker.patch.object(unit["unit_object"].machine, "entity_id", unit["machine"])

    mocker.patch.object(Model.units, "items").return_value = unit_list

    expected_partial_result = Partial(
        Severity.WARN,
        f"{main_unit} has units running on child machines: {child_unit}*",
    )

    # Run verifier against the first unit in the list
    verifier = BaseVerifier([units[0]["unit_object"]])
    result = verifier.check_has_sub_machines()

    assert expected_partial_result in result.partials
