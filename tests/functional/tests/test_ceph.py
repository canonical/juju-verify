"""Test deployment and functionality of juju-verify."""
import logging

from juju import loop
from tests.base import BaseTestCase

from juju_verify import juju_verify
from juju_verify.verifiers import get_verifier

logger = logging.getLogger()


class CephTests(BaseTestCase):
    """Functional testing for Ceph verifier."""

    # To add:
    # test not OK for two ceph-osd unit stops
    # test we get a warning when a machine also hosts another unit

    def test_single_osd_unit(self):
        """Test that shutdown of a single unit returns OK."""
        # juju-verify shutdown --units ceph-osd/1

        units = ['ceph-osd/0']
        check = 'shutdown'
        unit_objects = loop.run(juju_verify.find_units(self.model, units))
        verifier = get_verifier(unit_objects)
        result = verifier.verify(check)
        logger.info("result: %s", result)
        self.assertTrue(result.success)

    def test_single_mon_unit(self):
        """Test that shutdown of a single mon unit returns OK."""
        # juju-verify shutdown --units ceph-mon/0

        units = ['ceph-mon/0']
        check = 'shutdown'
        unit_objects = loop.run(juju_verify.find_units(self.model, units))
        verifier = get_verifier(unit_objects)
        result = verifier.verify(check)
        logger.info("result: %s", result)
        self.assertTrue(result.success)

    def test_two_mon_unit(self):
        """Test that shutdown of multiple mon units fails."""
        # juju-verify shutdown --units ceph-mon/0 ceph-mon/1

        units = ['ceph-mon/0', 'ceph-mon/1']
        check = 'shutdown'
        unit_objects = loop.run(juju_verify.find_units(self.model, units))
        verifier = get_verifier(unit_objects)
        result = verifier.verify(check)
        logger.info("result: %s", result)
        self.assertFalse(result.success)
