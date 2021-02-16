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

from unittest.mock import MagicMock, PropertyMock

from juju.model import Model
from juju.unit import Unit

from juju_verify.exceptions import VerificationError
from juju_verify.verifiers.base import BaseVerifier, Result, logger

import pytest


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
    assert result.format() == expected_msg


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
