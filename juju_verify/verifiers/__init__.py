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

"""Package with classes implementing verification methods for various charms."""
import logging
import os
from collections import defaultdict
from typing import Iterator, List

from juju.unit import Unit

from juju_verify.exceptions import CharmException
from juju_verify.utils.unit import parse_charm_name
from juju_verify.verifiers.base import BaseVerifier
from juju_verify.verifiers.ceph import CephMon, CephOsd
from juju_verify.verifiers.neutron_gateway import NeutronGateway
from juju_verify.verifiers.nova_compute import NovaCompute
from juju_verify.verifiers.result import Result, Severity

logger = logging.getLogger(__name__)


SUPPORTED_CHARMS = {
    "nova-compute": NovaCompute,
    "ceph-osd": CephOsd,
    "ceph-mon": CephMon,
    "neutron-gateway": NeutronGateway,
}


def get_verifiers(units: List[Unit]) -> Iterator[BaseVerifier]:
    """Implement Factory function "verifier" creator for the supplied units.

    :param units: Juju unit(s) for which you want to produce verifier
    :return: Correct verifier for given unit(s)
    :raises CharmException: Raised if units do not belong to the same charm or
        if the charm is unsupported for verification
    """
    if not units:
        raise CharmException("List of units can not be empty when creating verifier")

    charms = defaultdict(list)

    for unit in units:
        charm_type = parse_charm_name(unit.data.get("charm-url", ""))
        logger.debug("Inferred charm for unit %s: %s", unit.entity_id, charm_type)
        charms[charm_type].append(unit)

    for charm, charm_units in charms.items():
        logger.info("===[%s]===", ", ".join([unit.entity_id for unit in charm_units]))
        verifier = SUPPORTED_CHARMS.get(charm)
        if verifier is None:
            supported_charms = os.linesep.join(SUPPORTED_CHARMS.keys())
            logger.error(
                "Charm '%s' is not supported by juju-verify. Supported charms:%s%s",
                charm,
                os.linesep,
                supported_charms,
            )
            continue

        exclude_affected_units = list(set(units).difference(charm_units))
        logger.debug("Initiating verifier instance of class: %s", verifier.__name__)
        yield verifier(units=charm_units, exclude_affected_units=exclude_affected_units)
