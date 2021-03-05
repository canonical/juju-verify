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

logger = logging.getLogger(__name__)


class Result:  # pylint: disable=too-few-public-methods
    """Convenience class that represents result of the check."""

    def __init__(self, success: bool, reason: str = ''):
        """Set values of the check result.

        :param success: Indicates whether check passed or failed. True/False
        :param reason: Additional information about result. Can stay empty for
        positive results
        """
        self.success = success
        self.reason = reason

    def __str__(self) -> str:
        """Return formatted string representing the result."""
        result = 'OK' if self.success else 'FAIL'
        output = 'Result: {}'.format(result)
        if self.reason:
            output += '{}Reason: {}'.format(os.linesep, self.reason)
        return output

    def __add__(self, other: 'Result') -> 'Result':
        """Add together two Result instances.

        Boolean AND operation is applied on 'success' attribute and 'reason'
        attributes are concatenated.
        """
        if not isinstance(other, Result):
            raise NotImplementedError()

        new_success = self.success and other.success
        if other.reason and self.reason and not self.reason.endswith(
                os.linesep):
            self.reason += os.linesep
        new_reason = self.reason + other.reason

        return Result(new_success, new_reason)


def aggregate_results(*results: Result) -> Result:
    """Return aggregate value of multiple results."""
    result_list = list(results)
    final_result = result_list.pop(0)

    for result in result_list:
        final_result += result

    return final_result


def compare_results(*results: Result) -> bool:
    """Return boolean value if results are same."""
    result_list = list(results)
    comparative_result = result_list.pop(0)

    for result in results:
        if (comparative_result.success != result.success or
                comparative_result.reason != result.reason):
            return False

    return True
