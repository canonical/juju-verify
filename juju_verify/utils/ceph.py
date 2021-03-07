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
"""Base Ceph verification."""
import logging

from juju.unit import Unit

from juju_verify.exceptions import CharmException
from juju_verify.utils.action import data_from_action
from juju_verify.utils.unit import run_action_on_units
from juju_verify.verifiers.base import Result

logger = logging.getLogger()


def verify_ceph_mon_unit(*units: Unit) -> None:
    """Verify that units are from ceph-mon applications."""
    for unit in units:
        if "ceph-mon" not in unit.application:
            raise CharmException("Try to check the Ceph cluster health with no "
                                 "ceph-mon unit.")


def check_cluster_health(*units: Unit) -> Result:
    """Check Ceph cluster health for specific units.

    This will execute `get-health` against each unit provided.
    """
    verify_ceph_mon_unit(*units)
    result = Result(success=True)
    action_map = run_action_on_units(list(units), "get-health")
    for unit, action in action_map.items():
        cluster_health = data_from_action(action, "message")
        logger.info("Unit (%s): Ceph cluster health '%s'", unit, cluster_health)

        if "HEALTH_OK" in cluster_health and result.success:
            result += Result(True, f"{unit}: Ceph cluster is healthy")
        elif "HEALTH_WARN" in cluster_health or "HEALTH_ERR" in cluster_health:
            result += Result(False, f"{unit}: Ceph cluster is unhealthy")
        else:
            result += Result(False, f"{unit}: Ceph cluster is in an unknown state")

    if not action_map:
        result = Result(success=False, reason="Ceph cluster is in an unknown state")

    return result
