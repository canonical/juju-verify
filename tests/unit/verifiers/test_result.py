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
from copy import deepcopy

import pytest

from juju_verify.verifiers.result import Partial, Result, Severity, aggregate_results


@pytest.mark.parametrize(
    "severity, lesser_group, greater_group",
    [
        (Severity.OK, [], [Severity.WARN, Severity.UNSUPPORTED, Severity.FAIL]),
        (Severity.WARN, [Severity.OK], [Severity.UNSUPPORTED, Severity.FAIL]),
        (Severity.UNSUPPORTED, [Severity.OK, Severity.WARN], [Severity.FAIL]),
        (Severity.FAIL, [Severity.OK, Severity.WARN, Severity.UNSUPPORTED], []),
    ],
)
def test_severity_comparison(severity, lesser_group, greater_group):
    """Test ordering of the Severity enum values."""
    # test eq comparison
    assert severity == deepcopy(severity)

    # test that Severity can't be compared with other types
    raw_value = int(severity.value)
    assert severity != raw_value

    with pytest.raises(TypeError):
        _ = severity > 0

    with pytest.raises(TypeError):
        _ = severity < 100

    # Test ordering against other severity values
    for lesser_severity in lesser_group:
        assert severity > lesser_severity

    for greater_severity in greater_group:
        assert severity < greater_severity


@pytest.mark.parametrize(
    "severity",
    [
        Severity.OK,
        Severity.WARN,
        Severity.UNSUPPORTED,
        Severity.FAIL,
    ],
)
def test_partial_formatting(severity):
    """Test formatting of partial result."""
    msg = "foo"
    expected_str = f"[{severity.name}] {msg}"
    partial_result = Partial(severity, msg)

    assert str(partial_result) == expected_str


def test_partial_equal():
    """Test 'equal" operation between Partial instances."""
    # comparing with other types returns False
    assert Partial(Severity.OK, "foo") != "foo"

    # equal must match both severity and message
    severity = Severity.OK
    msg = "bar"
    assert Partial(severity, msg) == Partial(severity, msg)

    # Partials with different severities are not equal
    msg = "baz"
    assert Partial(Severity.OK, msg) != Partial(Severity.WARN, msg)

    # Partials with different messages are not equal
    severity = Severity.OK
    assert Partial(severity, "foo") != Partial(severity, "baz")


@pytest.mark.parametrize(
    "severity", [Severity.OK, Severity.WARN, Severity.UNSUPPORTED, Severity.FAIL]
)
def test_result_formatting(severity):
    """Test expected format of the Result.format()."""
    partial_result = Partial(severity, "foo")
    result = Result(partial_result.severity, partial_result.message)

    expected_success_msg = Result.VERBOSE_MAP.get(partial_result.severity)
    expected_msg = "Checks:{0}{1}{0}{0}Overall result: {2}".format(
        os.linesep, partial_result, expected_success_msg
    )

    assert str(result) == expected_msg


def test_result_empty_formatting():
    """Test expected format if Result is empty."""
    expected_msg = (
        "No result or additional information. This may be a bug in " '"juju-verify".'
    )
    assert str(Result()) == expected_msg


def test_result_add():
    """Test '+' operator on Result objects."""
    # Adding empty results, equals empty result
    result = Result() + Result()
    assert result == Result()

    # Adding empty and filled result
    result = Result(Severity.OK, "foo")
    assert result + Result() == result

    # Adding results with content
    result_1 = Result(Severity.OK, "foo")
    result_2 = Result(Severity.WARN, "bar")
    expect_result = Result()
    expect_result.add_partial_result(Severity.OK, "foo")
    expect_result.add_partial_result(Severity.WARN, "bar")
    assert result_1 + result_2 == expect_result


def test_result_iadd():
    """Test inplace '+' operation on Result Objects."""
    # Add empty Result
    empty_result = Result()
    empty_result += Result()
    assert empty_result == Result()

    # Add empty and filled result
    empty_result = Result()
    filled_result = Result(Severity.OK, "foo")
    empty_result += filled_result
    assert empty_result == filled_result

    # Add two filled results
    result_1 = Result(Severity.OK, "foo")
    result_2 = Result(Severity.WARN, "bar")
    expected_result = Result()
    expected_result.add_partial_result(Severity.OK, "foo")
    expected_result.add_partial_result(Severity.WARN, "bar")
    result_1 += result_2
    assert result_1 == expected_result


def test_result_adding_does_not_modifies_operands():
    """Test that '+' operation does not modify the original operands."""
    operand_1 = Result(Severity.OK, "foo")
    original_1 = deepcopy(operand_1)

    operand_2 = Result(Severity.WARN, "bar")
    original_2 = deepcopy(operand_2)

    _ = operand_1 + operand_2

    assert operand_1 == original_1
    assert operand_2 == original_2


def test_result_add_raises_not_implemented():
    """Test that '+' operator raises error if both operands aren't Result."""
    with pytest.raises(TypeError):
        _ = Result() + False

    with pytest.raises(TypeError):
        result = Result()
        result += False


def test_result_eq():
    """Test comparing two results."""
    # Compare with other type
    assert Result(Severity.OK, "foo") != "foo"
    # Compare empty results
    assert Result() == Result()
    assert Result() != Result(Severity.OK, "foo")

    # Compare results with content
    assert Result(Severity.OK, "foo") == Result(Severity.OK, "foo")
    assert Result(Severity.OK, "bar") != Result(Severity.OK, "foo")
    assert Result(Severity.FAIL, "foo") != Result(Severity.OK, "foo")

    # Compare results with multiple partial results
    result_original = Result()
    result_matching = Result()
    result_not_matching = Result()

    for result in (result_original, result_matching):
        result.add_partial_result(Severity.OK, "foo")
        result.add_partial_result(Severity.WARN, "bar")

    result_not_matching.add_partial_result(Severity.OK, "baz")
    result_not_matching.add_partial_result(Severity.FAIL, "quz")

    assert result_original == result_matching
    assert result_original != result_not_matching


def test_result_bool():
    """Test using Result in conditions."""
    default_result = Result(Severity.OK, "passed")
    result_1 = Result()
    result_2 = Result(Severity.OK, "test")

    assert not result_1, "result is not empty"
    assert (result_1 or default_result) == default_result

    assert result_2, "result is empty"
    assert (result_2 or default_result) != default_result


def test_result_add_partial_result():
    """Test method add_partial_result."""
    result = Result()

    expected_partials = [
        Partial(Severity.OK, "foo"),
        Partial(Severity.FAIL, "bar"),
    ]

    for partial in expected_partials:
        result.add_partial_result(partial.severity, partial.message)

    assert result.partials == expected_partials


def test_result_success():
    """Test overall results success value."""
    result = Result()
    # Special case: empty Result is True
    assert result.success

    # OK and WARN partial results still produces success == True
    result.add_partial_result(Severity.OK, "foo")
    assert result.success
    result.add_partial_result(Severity.WARN, "bar")
    assert result.success

    # UNSUPPORTED nad FAIL witll produce success == False
    result.add_partial_result(Severity.UNSUPPORTED, "baz")
    assert not result.success
    result.add_partial_result(Severity.FAIL, "quz")
    assert not result.success


@pytest.mark.parametrize(
    "result, expected_emptiness",
    [
        pytest.param(Result(), True, id="result-empty"),
        pytest.param(Result(Severity.OK, "foo"), False, id="result-not-empty"),
    ],
)
def test_result_empty(result, expected_emptiness):
    """Test expected values of Result.empty property."""
    assert result.empty == expected_emptiness


def test_aggregate_results():
    """Test aggregation of multiple results."""
    partial_1 = Partial(Severity.OK, "foo")
    partial_2 = Partial(Severity.WARN, "bar")
    partial_3 = Partial(Severity.UNSUPPORTED, "baz")
    partial_4 = Partial(Severity.FAIL, "quz")
    partial_list = [
        partial_1,
        partial_2,
        partial_3,
        partial_4,
    ]
    result_1 = Result(partial_1.severity, partial_1.message)
    result_2 = Result(partial_2.severity, partial_2.message)
    result_3 = Result(partial_3.severity, partial_3.message)
    result_4 = Result(partial_4.severity, partial_4.message)

    expected_result = Result()
    for partial in partial_list:
        expected_result.add_partial_result(partial.severity, partial.message)

    final_result = aggregate_results(
        result_1,
        result_2,
        result_3,
        result_4,
    )

    assert final_result == expected_result
