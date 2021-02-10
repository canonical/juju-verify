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

import pytest

from juju.unit import Unit
from juju.model import Model

from juju_verify.verifiers.base import BaseVerifier, Result
from juju_verify.exceptions import VerificationError


@pytest.mark.parametrize('success, reason',
                         [(True, 'Congratulation'),
                          (True, ''),
                          (False, 'FailReason')])
def test_result_formatting(success, reason):
    """Test expected format of the Result.format()"""
    result = Result(success, reason)
    common_str = 'Result: '
    success_str = 'OK' if success else 'FAIL'
    reason_str = '\nReason: {}'.format(reason) if reason else ''

    expected_msg = common_str + success_str + reason_str
    assert result.format() == expected_msg


def test_base_verifier_verify_no_units():
    """function 'verify' should fail if verifier has not units"""
    expected_msg = 'Can not run verification. This verifier ' \
                   'is not associated with any units.'
    verifier = BaseVerifier([])
    check = BaseVerifier.supported_checks()[0]

    with pytest.raises(VerificationError) as exc:
        verifier.verify(check)

    assert str(exc.value) == expected_msg


@pytest.mark.parametrize('check_name, check_method',
                         [('shutdown','verify_shutdown'),
                          ('reboot', 'verify_reboot')])
def test_base_verifier_supported_checks(mocker, check_name, check_method):
    """Test that each supported check executes expected method"""
    unit = Unit('foo', Model())
    mock_method = mocker.patch.object(BaseVerifier, check_method)

    verifier = BaseVerifier([unit])

    verifier.verify(check_name)
    mock_method.assert_called_once()


def test_base_verifier_unsupported_check():
    """Raise exception if check is unknown/unsupported"""
    unit = Unit('foo', Model())
    bad_check = 'bar'
    expected_msg = 'Unsupported verification check "{}" for charm ' \
                   '{}'.format(bad_check, BaseVerifier.NAME)

    verifier = BaseVerifier([unit])

    with pytest.raises(NotImplementedError) as exc:
        verifier.verify(bad_check)

    assert str(exc.value) == expected_msg


def test_base_verifier_not_implemented_checks():
    """Test that all checks raise NotImplemented in BaseVerifier"""
    unit = Unit('foo', Model())
    verifier = BaseVerifier([unit])

    for check in BaseVerifier.supported_checks():
        with pytest.raises(NotImplementedError):
            verifier.verify(check)


def test_base_verifier_unexpected_verify_error(mocker):
    """Test 'verify' raises VerificationError if case of unexpected failure"""
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
