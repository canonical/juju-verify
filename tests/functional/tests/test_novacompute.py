"""Test deployment and functionality of juju-verify."""
import logging

import zaza
from juju import loop
from tests.base import OpenstackBaseTestCase

from juju_verify.utils.unit import find_units
from juju_verify.verifiers import get_verifier
from juju_verify.verifiers.result import Partial, Severity

logger = logging.getLogger(__name__)


class NovaCompute(OpenstackBaseTestCase):
    """Functional tests of nova-compute verifier."""

    CHECK = "shutdown"
    APPLICATION_NAME = "nova-compute"
    RESOURCE_PREFIX = "juju-verify-nova-compute"

    def get_running_vms(self, nova_unit):
        """Return number of VM instances running on nova_unit.

        :param nova_unit: name of the nova-compute unit
        :return: number of running VMs
        :rtype: int
        :raises AssertionError: If 'instance-count' action fails on
                                nova-compute node.
        """
        result = zaza.model.run_action(nova_unit, "instance-count")
        self.assertEqual(result.status, "completed")
        instances = result.data.get("results", {}).get("instance-count")
        return int(instances)

    def test_single_unit(self):
        """Test that shutdown of a single unit returns OK."""
        units = ["nova-compute/0"]
        unit_objects = loop.run(find_units(self.model, units))
        verifier = get_verifier(unit_objects)
        result = verifier.verify(self.CHECK)
        logger.info("result: %s", result)
        self.assertTrue(result.success)

    def test_empty_az_fails(self):
        """Test that removing all computes from AZ fails the check.

        For this test, we assume that all nova-computes are part of the
        default availability zone ("nova"). Removing all nova-compute nodes
        should then trigger empty AZ error.
        """
        nova_application = self.model.applications.get("nova-compute")
        verifier = get_verifier(nova_application.units)
        expected_partial = Partial(
            Severity.FAIL,
            "Removing these units would leave "
            "following availability zones empty: "
            "{'nova'}",
        )
        result = verifier.verify(self.CHECK)
        logger.info("result: %s", result)
        self.assertFalse(result.success)
        self.assertTrue(expected_partial in result.partials)

    def test_running_vm_fails(self):
        """Test that check fails if there are running VMs on the compute."""
        logger.info("Starting new VM instance")
        self.launch_guest("blocking-vm")

        for nova_unit in zaza.model.get_units("nova-compute"):
            nova_unit_name = nova_unit.entity_id
            running_vms = self.get_running_vms(nova_unit_name)
            logger.info(
                "Checking nova unit: %s; Running VM's: %s", nova_unit_name, running_vms
            )
            if running_vms > 0:
                logger.debug("Selecting nova-compute unit '%s'", nova_unit_name)
                compute_with_vm = nova_unit_name
                break
        else:
            self.fail("Failed to find launched VM on any of the nova-compute units")

        expected_partial = Partial(
            Severity.FAIL, f"Unit {compute_with_vm} is running 1 VMs."
        )
        target_unit = loop.run(find_units(self.model, [compute_with_vm]))
        verifier = get_verifier(target_unit)

        result = verifier.verify(self.CHECK)
        logger.info("result: %s", result)
        self.assertFalse(result.success)
        self.assertTrue(expected_partial in result.partials)

        self.resource_cleanup()
