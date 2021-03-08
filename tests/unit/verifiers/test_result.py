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
"""Result class and related function test suite."""
import os

import pytest

from juju_verify.verifiers import Result
from juju_verify.verifiers.result import aggregate_results


@pytest.mark.parametrize('success, reason',
                         [(True, 'Congratulation'),
                          (True, ''),
                          (False, 'FailReason')])
def test_result_formatting(success, reason):
    """Test expected format of the Result.format()."""
    result = Result(success, reason)
    common_str = 'Result: '
    success_str = 'OK' if success else 'FAIL'
    reason_str = '{}Reason: {}'.format(os.linesep, reason) if reason else ''

    expected_msg = common_str + success_str + reason_str
    assert str(result) == expected_msg


@pytest.mark.parametrize('result_1, result_2, expect_result',
                         [(Result(True, 'foo'), Result(True, 'bar'),
                           Result(True, f'foo{os.linesep}bar')),
                          (Result(True, ''), Result(False, 'foo'), Result(False, 'foo')),
                          (Result(False, 'foo'), Result(True, ''), Result(False, 'foo')),
                          (Result(False, f'foo{os.linesep}'), Result(False, 'bar'),
                           Result(False, f'foo{os.linesep}bar'))])
def test_result_add(result_1, result_2, expect_result):
    """Test '+' operator on Result objects."""
    result = result_1 + result_2

    assert result == expect_result


def test_result_add_raises_not_implemented():
    """Test that '+' operator raises error if both operands aren't Result."""
    with pytest.raises(TypeError):
        _ = Result(True) + False


@pytest.mark.parametrize("result_1, result_2, exp_eq", [
    (Result(True), Result(False), False),
    (Result(True, reason="test_1"), Result(False, reason="test_2"), False),
    (Result(True, reason="test_1"), Result(True, reason="test_2"), False),
    (Result(True), Result(True), True),
    (Result(True, reason="test"), Result(True, reason="test"), True),
    (Result(True), 0, False),
    (Result(True), 0.0, False),
    (Result(True), "test", False),
    (Result(True), False, False),
])
def test_result_eq(result_1, result_2, exp_eq):
    """Test comparing two results."""
    assert (result_1 == result_2) == exp_eq


@pytest.mark.parametrize("results, exp_result", [
    ([Result(True), Result(True)], Result(True)),
    ([Result(True), Result(False)], Result(False)),
    ([Result(True, "test_1"), Result(False, "test_2")],
     Result(False, os.linesep.join(["test_1", "test_2"]))),
    ([Result(True, "test_1"), Result(True, "test_2")],
     Result(True, os.linesep.join(["test_1", "test_2"]))),
])
def test_aggregate_results(results, exp_result):
    """Test aggregation of multiple results."""
    assert aggregate_results(*results) == exp_result
