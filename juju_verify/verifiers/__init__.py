"""Package containing classes that implement verification methods for various
charms"""
import re
import logging
from typing import List

from juju.unit import Unit

from juju_verify.exceptions import CharmException
from .base import BaseVerifier
from .nova_compute import NovaCompute
from .ceph_osd import CephOsd

logger = logging.getLogger(__name__)


SUPPORTED_CHARMS = {
    'nova-compute': NovaCompute,
    'ceph-osd': CephOsd,
}


CHARM_URL_PATTERN = re.compile(r'^(.*):(.*/)?(?P<charm>.*)(-\d+)$')


def get_verifier(units: List[Unit]) -> BaseVerifier:
    """ Factory function to create "verifier" for the supplied units.

    :param units: Juju unit(s) for which you want to produce verifier
    :return: Correct verifier for given unit(s)
    :raises CharmException: Raised if units do not belong to the same charm or
    if the charm is unsupported for verification
    """
    def parse_charm_name(charm_url: str) -> str:
        """Parses charm name from full charm url.

        Example: 'cs:focal/nova-compute-141' -> 'nova-compute'
        """
        match = CHARM_URL_PATTERN.match(charm_url)
        if match is None:
            raise CharmException('Failed to parse charm-url: '
                                 '"{}"'.format(charm_url))
        return match.group('charm')

    charm_types = set()

    for unit in units:
        charm_type = parse_charm_name(unit.data.get('charm-url', ''))
        logger.debug('Inferred charm for unit %s: %s', unit.entity_id,
                     charm_type)
        charm_types.add(charm_type)

    if len(charm_types) > 1:
        raise CharmException('Units are not running same charm. '
                             'Detected types: {}'.format(charm_types))

    if len(charm_types) < 1:
        raise CharmException('Failed to detect charm running on the selected '
                             'units.')
    charm = charm_types.pop()

    verifier = SUPPORTED_CHARMS.get(charm)

    if verifier is None:
        supported_charms = '\n'.join(SUPPORTED_CHARMS.keys())
        raise CharmException('Charm "{}" is not supported by juju-verify. '
                             'Supported charms:\n'
                             '{}'.format(charm, supported_charms))
    logger.debug('Initiating verifier instance of class: %s',
                 verifier.__name__)
    return verifier(units=units)
