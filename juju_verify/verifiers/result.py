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
"""Juju-verify verification result."""
import logging
import os
from enum import Enum
from functools import total_ordering
from json import JSONDecodeError
from typing import Any, Callable, Dict, List, Tuple, Union

from juju_verify.exceptions import CharmException, JujuActionFailed

logger = logging.getLogger(__name__)
STOP_ON_FAILURE: bool = False


def stop_on_failure() -> bool:
    """Get the configuration to stop on failure."""
    return STOP_ON_FAILURE


def set_stop_on_failure(stop: bool = False) -> None:
    """Set stop on failure."""
    global STOP_ON_FAILURE  # pylint: disable=W0603
    STOP_ON_FAILURE = stop


@total_ordering
class Severity(Enum):
    """Collection of possible Result's severities."""

    OK = 10
    WARN = 20
    UNSUPPORTED = 30
    FAIL = 40

    def __lt__(self, other: object) -> bool:
        """Perform "less than" comparison with other Severity instances."""
        if not isinstance(other, Severity):
            return NotImplemented

        return self.value < other.value  # pylint: disable=W0143


class Partial:
    """Class representing partial result.

    Generally, instances of this class are used in Result class to represent (partial)
    results of individual checks ran during the whole verification process.
    """

    def __init__(self, severity: Severity, message: str):
        """Initialize Partial instance.

        :param severity: Severity of the partial result.
        :param message: Additional information about the result
        """
        self.severity = severity
        self.message = message

    def __str__(self) -> str:
        """Return string representation of the Partial class instance."""
        return f"[{self.severity.name}] {self.message}"

    def __eq__(self, other: object) -> bool:
        """Perform equal comparison with another Partial instance."""
        if not isinstance(other, Partial):
            return NotImplemented

        return self.severity == other.severity and self.message == other.message


class Result:
    """Convenience class that represents result of the check.

    Each juju-verify check should return Result instance with at least one partial
    result in self.partials. Multiple partial result are good idea if, for example, the
    check runs against multiple units.
    """

    VERBOSE_MAP = {
        Severity.OK: "OK (All checks passed)",
        Severity.WARN: "OK (Checks passed with warnings)",
        Severity.UNSUPPORTED: "Failed (Targeted charms are not supported)",
        Severity.FAIL: "Failed",
    }

    def __init__(self, severity: Severity = Severity.OK, message: str = ""):
        """Initialize result instance.

        Initial arguments 'severity' and 'message' will automatically create Partial
        result that will be stored in the self.partials. Additional partial results can
        be added via self.add_partial_result.
        For convenience, it's possible to initiate empty Result, however keep in mind
        that returning empty Result is not very helpful.

        :param severity: Severity of the result
        :param message: Additional information about the result.
        """
        self.partials: List[Partial] = []
        if message:
            self.partials.append(Partial(severity, message))

    def __str__(self) -> str:
        """Return formatted string representing the result.

        Note: If the Result instance has no Partial results in self.partials, returned
        string will be error message.
        """
        if not self.partials:
            return (
                "No result or additional information. This may be a bug in "
                "'juju-verify'."
            )
        output = f"Checks:{os.linesep}"
        for partial in self.partials:
            output += f"{partial}{os.linesep}"
        output += os.linesep

        max_severity = max(partial.severity for partial in self.partials)
        output += f"Result: {self.VERBOSE_MAP.get(max_severity)}{os.linesep}"
        return output

    def __add__(self, other: object) -> "Result":
        """Perform "add" operation with another Result instance."""
        if not isinstance(other, Result):
            return NotImplemented
        new_obj = Result()

        for partial in self.partials + other.partials:
            new_obj.partials.append(partial)

        return new_obj

    def __iadd__(self, other: object) -> "Result":
        """Perform "inplace add" operation with another Result instance."""
        if not isinstance(other, Result):
            return NotImplemented

        for partial in other.partials:
            self.partials.append(partial)
        return self

    def __eq__(self, other: object) -> bool:
        """Compare two Result instances."""
        if not isinstance(other, Result):
            return NotImplemented

        return self.partials == other.partials and self.success == other.success

    def __bool__(self) -> bool:
        """Return True if result does contain any partial results."""
        return bool(self.partials)

    @property
    def success(self) -> bool:
        """Return overall Result's success.

        The success is calculated based on the highest Severity value from all the
        partial results in self.partials. Following is the map for overall success:

        Highest severity is OK -> Overall success is True
        Highest severity is WARN -> Overall success is True
        Highest severity is UNSUPPORTED -> Overall success is False
        Highest severity is FAIL -> Overall success is False

        Note: If the Result instance has no Partial results in self.partials, overall
        success will be True.
        """
        return all(partial.severity < Severity.UNSUPPORTED for partial in self.partials)

    @property
    def empty(self) -> bool:
        """Return True if result does not contain any partial results."""
        return not bool(self.partials)

    def add_partial_result(self, severity: Severity, message: str) -> None:
        """Add partial result to this instance."""
        self.partials.append(Partial(severity, message))


def checks_executor(
    *checks: Union[Callable, Tuple[Callable, Dict[str, Any]]]
) -> Result:
    """Executor that aggregates checks and captures errors.

    This executor will accept checks as a callable function or as a tuple with first
    object callable (check) and second as a dictionary containing parameters for
    performing the check. The executor's output aggregates all check results into one
    result, while the order is preserved. If the check does not return any input, then
    the default value is used in the form:
    `Result(OK, "<check .__ name __> check successful").
    At the same time, if the check fails on one of the following errors
    (JujuActionFailed, CharmException, KeyError, JSONDecodeError), it will be marked
    as failed with the result in the form:
    `Result(FAIL, f"{check.__name__} check failed with error: {error}"`.

    Examples of use:

    def check_without_parameter_1():
        return Result(Severity.OK, "check 1 passed")

    def check_without_parameter_2():
        return Result(Severity.OK, "check 2 passed")

    def check_with_parameter(resources=None):
        if resources is None:
            return Result(Severity.FAIL, "check 3 failed")

        return Result(Severity.OK, f"check 3 passed ({resources})")

    result_1 = checks_executor(check_without_parameter_1,
                               check_without_parameter_2,
                               (check_with_parameter, dict(resources="DHCP")))

    print(result_1)
    Checks:
    [OK] check 1 passed
    [OK] check 2 passed
    [OK] check 3 passed (DHCP)

    Overall result: OK (All checks passed)

    result_2 = checks_executor(check_without_parameter_1,
                               check_without_parameter_2,
                               check_with_parameter)

    print(result_2)
    Checks:
    [OK] check 1 passed
    [OK] check 2 passed
    [FAIL] check 3 failed

    Overall result: Failed
    """
    aggregate_result = Result()
    for check_definition in checks:
        # split check definition into check and parameters
        if callable(check_definition):
            check: Callable = check_definition
            check_kwargs: Dict = {}
        else:
            check, check_kwargs = check_definition

        check_name = getattr(check, "__name__", "unknown")

        try:
            logger.debug("check %s is executed", check_name)
            aggregate_result += check(**check_kwargs) or Result(
                Severity.OK, f"{check_name} check passed"
            )
            logger.debug("check %s ended successfully", check_name)
        except (JujuActionFailed, CharmException, KeyError, JSONDecodeError) as error:
            aggregate_result += Result(
                Severity.FAIL, f"{check_name} check failed with error: {error}"
            )
            logger.debug("check %s failed with error: %s", check_name, str(error))

        if not aggregate_result.success and stop_on_failure():
            # break if verify was called with the `--stop-on-failure` flag
            break

    return aggregate_result
