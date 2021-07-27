"""Test deployment and functionality of juju-verify."""
import logging
import re

import tenacity
import zaza
from juju import loop
from tests.base import BaseTestCase

from juju_verify import juju_verify
from juju_verify.utils.action import cache
from juju_verify.verifiers import get_verifier
from juju_verify.verifiers.ceph import CephCommon
from juju_verify.verifiers.result import Result

logger = logging.getLogger()


class CephOsdTests(BaseTestCase):
    """Functional testing for ceph-osd verifier."""

    test_pool = "test"

    # TODO: add test to check_availability_zone after new approach

    def _add_test_pool(self, percent_data: int = 10):
        """Add a test pool."""
        _ = zaza.model.run_action(
            "ceph-mon/0",
            "create-pool",
            action_params={"name": self.test_pool, "percent-data": percent_data},
        )

    def _remove_test_pool(self):
        """Delete a test pool."""
        _ = zaza.model.run_action(
            "ceph-mon/0", "delete-pool", action_params={"name": self.test_pool}
        )

    @tenacity.retry(wait=tenacity.wait_exponential(max=60))
    def _wait_to_healthy_ceph_cluster(self):
        """Wait to Ceph cluster be healthy again."""
        unit_objects = loop.run(juju_verify.find_units(self.model, ["ceph-mon/0"]))
        result = CephCommon.check_cluster_health(*unit_objects)
        assert result.success

    def assert_message_in_result(self, exp_message: str, result: Result):
        """Assert that message is in partials results."""
        self.assertTrue(
            any(re.match(exp_message, str(partial)) for partial in result.partials)
        )

    def test_single_osd_unit(self):
        """Test that shutdown of a single ceph-osd unit returns OK."""
        # juju-verify shutdown --units ceph-osd/1

        units = ["ceph-osd/0"]
        check = "shutdown"
        unit_objects = loop.run(juju_verify.find_units(self.model, units))
        verifier = get_verifier(unit_objects)
        result = verifier.verify(check)
        logger.info("result: %s", result)
        self.assertTrue(result.success)
        self.assert_message_in_result(
            r"\[WARN\] ceph-osd\/\d has units running on child machines: ceph-mon\/\d",
            result,
        )

    def test_two_osd_unit(self):
        """Test that shutdown of multiple ceph-osd units fails."""
        # juju-verify shutdown --units ceph-osd/0 ceph-osd/1

        units = ["ceph-osd/0", "ceph-osd/1"]
        check = "shutdown"
        unit_objects = loop.run(juju_verify.find_units(self.model, units))
        verifier = get_verifier(unit_objects)
        result = verifier.verify(check)
        logger.info("result: %s", result)
        self.assertFalse(result.success)
        self.assert_message_in_result(
            r"\[FAIL\] It's not safe to removed units {'ceph-osd\/\d', 'ceph-osd\/\d'} "
            r"in the availability zone 'root=default'. "
            r"\[free_units=1, inactive_units=0\]",
            result,
        )

    def test_check_ceph_cluster_health_passed(self):
        """Test that shutdown of a single ceph-osd unit returns OK."""
        # juju-verify shutdown --units ceph-osd/1
        units = ["ceph-osd/0"]
        check = "shutdown"
        unit_objects = loop.run(juju_verify.find_units(self.model, units))

        self._add_test_pool(percent_data=80)
        self._wait_to_healthy_ceph_cluster()
        # check that Ceph cluster is healthy
        verifier = get_verifier(unit_objects)
        result = verifier.verify(check)
        logger.info("result: %s", result)
        self.assertTrue(result.success)
        self.assert_message_in_result(
            r"\[OK\] ceph-mon\/\d: Ceph cluster is healthy", result
        )

        self._remove_test_pool()

    def test_check_ceph_cluster_health_failed(self):
        """Test that shutdown of a single ceph-osd unit fails."""
        # juju-verify shutdown --units ceph-osd/1
        units = ["ceph-osd/0"]
        check = "shutdown"
        unit_objects = loop.run(juju_verify.find_units(self.model, units))

        self._add_test_pool()
        # check that Ceph cluster is unhealthy
        verifier = get_verifier(unit_objects)
        result = verifier.verify(check)
        logger.info("result: %s", result)
        self.assertFalse(result.success)
        self.assert_message_in_result(
            r"\[FAIL\] ceph-mon\/\d: Ceph cluster is unhealthy", result
        )

        self._remove_test_pool()

    def test_check_replication_number(self):
        """Test that shutdown of a single ceph-osd unit returns OK."""
        # juju-verify shutdown --units ceph-osd/1
        units = ["ceph-osd/0", "ceph-osd/1"]
        check = "shutdown"
        unit_objects = loop.run(juju_verify.find_units(self.model, units))

        self._add_test_pool()
        # check that check_replication_number failed, due default min_size=2
        verifier = get_verifier(unit_objects)
        result = verifier.verify(check)
        logger.info("result: %s", result)
        self.assertFalse(result.success)
        self.assert_message_in_result(
            r"\[FAIL\] The minimum number of replicas in 'ceph-osd' is 1 and "
            r"it's not safe to restart\/shutdown 2 units. 0 units "
            r"are not active.",
            result,
        )

        # change min_size to 1
        _ = zaza.model.run_action(
            "ceph-mon/0",
            "pool-set",
            action_params={"name": "test", "key": "min_size", "value": "1"},
        )
        # clear cache
        cache.clear()
        # check that check_replication_number passed
        verifier = get_verifier(unit_objects)
        result = verifier.verify(check)
        logger.info("result: %s", result)
        self.assertFalse(result.success)
        self.assert_message_in_result(
            r"\[OK\] Minimum replica number check passed.", result
        )

        self._remove_test_pool()


class CephMonTests(BaseTestCase):
    """Functional testing for ceph-osd verifier."""

    def test_single_mon_unit(self):
        """Test that shutdown of a single mon unit returns OK."""
        # juju-verify shutdown --units ceph-mon/0

        units = ["ceph-mon/0"]
        check = "shutdown"
        unit_objects = loop.run(juju_verify.find_units(self.model, units))
        verifier = get_verifier(unit_objects)
        result = verifier.verify(check)
        logger.info("result: %s", result)
        self.assertTrue(result.success)

    def test_two_mon_unit(self):
        """Test that shutdown of multiple mon units fails."""
        # juju-verify shutdown --units ceph-mon/0 ceph-mon/1

        units = ["ceph-mon/0", "ceph-mon/1"]
        check = "shutdown"
        unit_objects = loop.run(juju_verify.find_units(self.model, units))
        verifier = get_verifier(unit_objects)
        result = verifier.verify(check)
        logger.info("result: %s", result)
        self.assertFalse(result.success)
