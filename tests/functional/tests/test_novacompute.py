"""Test deployment and functionality of juju-verify."""

from juju import loop
from tests.base import BaseTestCase

from juju_verify import juju_verify
from juju_verify.verifiers import get_verifier


class NovaCompute(BaseTestCase):
    """Base class for functional testing of nova-compute verifier."""

    def test_single_unit(self):
        """Test that shutdown of a single unit returns OK."""
        units = ['nova-compute/0']
        check = 'shutdown'
        unit_objects = loop.run(juju_verify.find_units(self.model, units))
        verifier = get_verifier(unit_objects)
        result = verifier.verify(check)
        print(str(result))
