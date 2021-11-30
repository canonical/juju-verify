"""Generic setup for functional tests."""
import logging
import unittest

import zaza.model
from juju import loop
from zaza.openstack.charm_tests.test_utils import OpenStackBaseTest

from juju_verify import cli
from juju_verify.utils.action import cache

logger = logging.getLogger(__name__)


class BaseTestCase(unittest.TestCase):
    """Base class for functional testing of verifiers."""

    def tearDown(self) -> None:
        """Teardown after each test."""
        cache.clear()
        logger.debug("cache was cleared")

    @classmethod
    def setUpClass(cls):
        """Run class setup for running tests."""
        super(BaseTestCase, cls).setUpClass()
        cls.model = loop.run(cli.connect_model(zaza.model.CURRENT_MODEL))

    @classmethod
    def tearDownClass(cls):
        """Teardown class after running tests."""
        loop.run(cls.model.disconnect())


class OpenstackBaseTestCase(BaseTestCase, OpenStackBaseTest):
    """Base class for functional testing of OpenStack charms verifiers."""

    APPLICATION_NAME = None

    @classmethod
    def setUpClass(cls):
        """Run class setup for running tests."""
        BaseTestCase.setUpClass()
        OpenStackBaseTest.setUpClass(application_name=cls.APPLICATION_NAME)

    @classmethod
    def tearDownClass(cls):
        """Teardown class after running tests."""
        BaseTestCase.tearDownClass()
        OpenStackBaseTest.tearDownClass()
