"""Test deployment and functionality of juju-verify."""

from juju import loop
from tests.base import BaseTestCase

from juju_verify import juju_verify
from juju_verify.verifiers import get_verifier


class CephTests(BaseTestCase):
    """Base class for functional testing."""

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
        self.assertTrue(result.success is True)
