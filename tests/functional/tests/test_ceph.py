"""Test deployment and functionality of juju-verify."""
import logging
import re
from typing import Optional

import tenacity
import zaza
from tests.base import BaseTestCase

from juju_verify.utils.action import cache_manager
from juju_verify.verifiers import get_verifiers
from juju_verify.verifiers.result import Result

logger = logging.getLogger(__name__)


class CephOsdTests(BaseTestCase):
    """Functional testing for ceph-osd verifier."""

    def setUp(self):
        """Disable cache for all ceph-osd tests."""
        cache_manager.disable()  # disable cache for all run action
        self.pools = []  # list of pools created in tests

    def tearDown(self):
        """Remove all pools."""
        for pool in self.pools:
            self._remove_pool(pool)

    def _add_pool(
        self,
        name: str,
        crush_rule: Optional[str] = None,
        percent_data: Optional[int] = None,
    ):
        """Add pool."""
        action_params = {
            "name": name,
            "profile-name": crush_rule,
            "percent-data": percent_data,
        }
        _ = zaza.model.run_action(
            "ceph-mon/0",
            "create-pool",
            action_params={
                param: value for param, value in action_params.items() if value
            },
        )
        # NOTE (rgildein): The create-pool action ignores the profile-name.
        # https://bugs.launchpad.net/charm-ceph-mon/+bug/1905573
        if crush_rule:
            _ = zaza.model.run_action(
                "ceph-mon/0",
                "pool-set",
                action_params={"name": name, "key": "crush_rule", "value": crush_rule},
            )
        self.pools.append(name)
        logger.info(
            "Add pool `%s` with crush rule `%s` and percent_data=%s",
            name,
            crush_rule,
            percent_data,
        )

    @staticmethod
    def _remove_pool(name: str):
        """Delete pool."""
        _ = zaza.model.run_action(
            "ceph-mon/0", "delete-pool", action_params={"name": name}
        )
        logger.info("Remove pool `%s`", name)

    @tenacity.retry(
        wait=tenacity.wait_exponential(max=60), stop=tenacity.stop_after_attempt(8)
    )
    def _wait_to_ceph_cluster(self, state: str = "HEALTH_OK"):
        """Wait to Ceph cluster be in specific status."""
        logger.info("waiting to Ceph cluster be in %s state", state)
        ceph_health = zaza.model.run_action("ceph-mon/0", "get-health")
        ceph_health_message = ceph_health.data.get("results", {}).get("message", "")
        logger.info("Ceph cluster health message: %s", ceph_health_message)
        assert state in ceph_health_message

    def assert_message_in_result(self, exp_message: str, result: Result):
        """Assert that message is in partials results."""
        self.assertTrue(
            any(re.match(exp_message, str(partial)) for partial in result.partials)
        )

    def test_single_osd_unit(self):
        """Test that shutdown of a single ceph-osd unit returns OK."""
        # juju-verify shutdown --units ceph-osd/1
        units = [self.model.units["ceph-osd-hdd/0"]]
        check = "shutdown"
        self._wait_to_ceph_cluster()
        verifier = next(get_verifiers(units))
        result = verifier.verify(check)
        logger.info("result: %s", result)
        self.assertTrue(result.success)

    def test_pool_with_multiple_failure_domain(self):
        """Test multiple pools with different failure-domain."""
        # juju-verify shutdown --units ceph-osd/0 ceph-osd/1
        units = [self.model.units["ceph-osd-hdd/0"]]
        check = "shutdown"
        self._add_pool("pool-hdd-replication", "hdd-host", 50)
        self._add_pool("pool-ssd-replication", "ssd-rack", 50)
        self._wait_to_ceph_cluster()
        verifier = next(get_verifiers(units))
        result = verifier.verify(check)
        logger.info("result: %s", result)
        self.assertFalse(result.success)
        self.assert_message_in_result(
            r"\[FAIL\] Juju-verify only supports crush rules with same failure-domain "
            r"for now.",
            result,
        )

    def test_check_ceph_cluster_health_passed(self):
        """Test that shutdown of a single ceph-osd unit returns OK."""
        # juju-verify shutdown --units ceph-osd/1
        units = [self.model.units["ceph-osd-hdd/0"]]
        check = "shutdown"
        self._add_pool("test-healthy-cluster", percent_data=80)
        self._wait_to_ceph_cluster()
        # check that Ceph cluster is healthy
        verifier = next(get_verifiers(units))
        result = verifier.verify(check)
        logger.info("result: %s", result)
        self.assertTrue(result.success)
        self.assert_message_in_result(
            r"\[OK\] ceph-mon\/\d: Ceph cluster is healthy", result
        )

    def test_check_ceph_cluster_health_warning(self):
        """Test warning result for shutdown of a single ceph-osd unit."""
        # juju-verify shutdown --units ceph-osd/1
        units = [self.model.units["ceph-osd-hdd/0"]]
        check = "shutdown"
        self._add_pool("test-warn-cluster", "hdd-host")
        self._wait_to_ceph_cluster("HEALTH_WARN")
        # check that Ceph cluster is unhealthy
        verifier = next(get_verifiers(units))
        result = verifier.verify(check)
        logger.info("result: %s", result)
        self.assert_message_in_result(
            r"\[FAIL\] ceph-mon\/\d: Ceph cluster is in a warning state",
            result,
        )

    def test_replication_number(self):
        """Test that shutdown of multiple ceph-osd units pass/fails."""
        # juju-verify shutdown --units ceph-osd/0 ceph-osd/1
        check = "shutdown"
        self._add_pool("hdd-replication", "hdd", 50)
        self._wait_to_ceph_cluster()

        # try to remove two units w/ device-class == hdd
        units = [self.model.units["ceph-osd-hdd/0"], self.model.units["ceph-osd-hdd/1"]]
        verifier = next(get_verifiers(units))
        result = verifier.verify(check)
        logger.info("result: %s", result)
        self.assertFalse(result.success)
        self.assert_message_in_result(
            r"\[FAIL\] The minimum number of replicas in `ceph-osd-hdd` and pool "
            r"`hdd-replication` is 2 and it's not safe to reboot\/shutdown "
            r"ceph-osd-hdd/\d, ceph-osd-hdd/\d units.",
            result,
        )

        # try to remove two units w/ device-class == ssd
        units = [self.model.units["ceph-osd-ssd/0"], self.model.units["ceph-osd-ssd/1"]]
        verifier = next(get_verifiers(units))
        result = verifier.verify(check)
        logger.info("result: %s", result)  # passes because there is no pool using ssd
        self.assertTrue(result.success)

        # try to remove two units, but one w/ device-class hdd and another w/ ssd
        units = [self.model.units["ceph-osd-hdd/0"], self.model.units["ceph-osd-ssd/0"]]
        verifier = next(get_verifiers(units))
        result = verifier.verify(check)
        logger.info("result: %s", result)
        self.assertTrue(result.success)
        self.assert_message_in_result(
            r"\[OK\] Minimum replica number check passed.",
            result,
        )
        self.assert_message_in_result(
            r"\[OK\] Availability zone check passed.",
            result,
        )


class CephMonTests(BaseTestCase):
    """Functional testing for ceph-osd verifier."""

    def test_single_mon_unit(self):
        """Test that shutdown of a single mon unit returns OK."""
        # juju-verify shutdown --units ceph-mon/0

        units = [self.model.units["ceph-mon/0"]]
        check = "shutdown"
        verifier = next(get_verifiers(units))
        result = verifier.verify(check)
        logger.info("result: %s", result)
        self.assertTrue(result.success)

    def test_two_mon_unit(self):
        """Test that shutdown of multiple mon units fails."""
        # juju-verify shutdown --units ceph-mon/0 ceph-mon/1

        units = [self.model.units["ceph-mon/0"], self.model.units["ceph-mon/1"]]
        check = "shutdown"
        verifier = next(get_verifiers(units))
        result = verifier.verify(check)
        logger.info("result: %s", result)
        self.assertFalse(result.success)
