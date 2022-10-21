"""Test deployment and functionality of juju-verify with ovn-central charm."""
import logging

from tests.base import BaseTestCase

from juju_verify.verifiers import BaseVerifier, get_verifiers
from juju_verify.verifiers.result import Partial, Severity

logger = logging.getLogger(__name__)


class OvnCentralTests(BaseTestCase):
    """Functional tests of ovn-central verifier."""

    APPLICATION_NAME = "ovn-central"
    # TODO: Remove once the changes to ovn-central are merged and we'll stop using
    #  custom charm
    APP_MAP = [("ovn-central", "ovn-central")]

    def get_verifier(self, number_of_units: int) -> BaseVerifier:
        """Return OVN central verifier for number of specified units."""
        ovn_units = self.model.applications.get(self.APPLICATION_NAME).units
        target_units = ovn_units[0:number_of_units]
        verifier = next(get_verifiers(target_units, self.APP_MAP))

        return verifier

    def test_reboot_ok(self):
        """Test requesting reboot of 1 unit which should return OK result.

        Testing cluster has 5 units so expected outcome of rebooting 1 is OK.
        """
        verifier = self.get_verifier(1)
        result = verifier.verify_reboot()

        self.assertTrue(result.success)

    def test_reboot_warn(self):
        """Test requesting reboot of 2 units which should return OK result with warning.

        Testing cluster has 5 units so requesting reboot of 2 units should be OK with
        additional warning that cluster won't be able to tolerate any more failures.
        """
        expected_warning = Partial(
            Severity.WARN,
            "While the rebooted units are down, this cluster won't be able to tolerate "
            "any more failures.",
        )

        verifier = self.get_verifier(2)
        result = verifier.verify_reboot()

        self.assertTrue(result.success)
        self.assertIn(expected_warning, result.partials)

    def test_reboot_fail(self):
        """Test requesting reboot of 3 units which should return FAIL result.

        Testing cluster has 5 units, and it should not allow reboot of 3 units as it will
        bring it below quorum minimum.
        """
        verifier = self.get_verifier(3)
        result = verifier.verify_reboot()

        self.assertFalse(result.success)

    def test_shutdown_ok(self):
        """Test requesting shutdown of 1 unit which should return OK result with warning.

        Permanently downscaling cluster of 5 by one should return OK with warning to the
        user that cluster tolerance will be reduced from 2 to 1 node.
        """
        all_units = len(self.model.applications.get(self.APPLICATION_NAME).units)
        units_to_remove = 1
        expected_warn = Partial(
            Severity.WARN,
            f"Removing {units_to_remove} units from cluster of {all_units} will decrease"
            f" its fault tolerance from 2 to 1.",
        )

        verifier = self.get_verifier(1)
        result = verifier.verify_shutdown()

        self.assertTrue(result.success)
        self.assertIn(expected_warn, result.partials)

    def test_shutdown_fail(self):
        """Test requesting shutdown of 3 unit which should return FAIL result.

        Permanently downscaling cluster of 5 by 3 should return FAIL result as it would
        bring the cluster's fault tolerance to 0
        """
        verifier = self.get_verifier(3)
        result = verifier.verify_shutdown()

        self.assertFalse(result.success)
