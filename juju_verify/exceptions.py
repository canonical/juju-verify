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

"""Collection of juju verification exceptions."""
import os
from typing import Any, Dict, Optional

from juju.errors import JujuError
from juju.unit import Unit


class VerificationError(Exception):
    """Exception related to the main verification process."""


class CharmException(Exception):
    """Exception related to the charm or the unit that runs it."""


class JujuVerifyError(Exception):
    """Exception related to the main logic of Juju-verify."""


class JujuActionFailed(Exception):
    """Exception related to failing action run on the unit."""

    def __init__(
        self,
        error: JujuError,
        unit: Unit,
        action: str,
        params: Optional[Dict[str, Any]] = None,
    ):
        """Initialize JujuActionFailed error message."""
        params = params or {}
        params_str = " ".join(f"{name}={value}" for name, value in params.items())
        juju_error_message = os.linesep.join(f"  {err}" for err in error.errors)
        self.message = (
            f"{unit.entity_id}: action `{action} {params_str}` failed "
            f"with errors:{os.linesep}{juju_error_message}"
        )
        super().__init__(self.message)
