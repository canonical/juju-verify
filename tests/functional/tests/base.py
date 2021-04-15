"""Generic setup for functional tests."""

import unittest

from juju import loop
from zaza.openstack.charm_tests.test_utils import OpenStackBaseTest
import zaza.model

from juju_verify import juju_verify


class BaseTestCase(unittest.TestCase):
    """Base class for functional testing of verifiers."""

    @classmethod
    def setUpClass(cls):
        """Run class setup for running tests."""
        super(BaseTestCase, cls).setUpClass()
        cls.log_level = 'info'
        juju_verify.config_logger(cls.log_level)
        cls.model = loop.run(juju_verify.connect_model(zaza.model.CURRENT_MODEL))

    @classmethod
    def tearDownClass(cls):
        loop.run(cls.model.disconnect())


class OpenstackBaseTestCase(BaseTestCase, OpenStackBaseTest):

    APPLICATION_NAME = None

    @classmethod
    def setUpClass(cls):
        BaseTestCase.setUpClass()
        OpenStackBaseTest.setUpClass(application_name=cls.APPLICATION_NAME)

    @classmethod
    def tearDownClass(cls):
        super(BaseTestCase, cls).tearDownClass()
        super(OpenstackBaseTestCase, cls).tearDownClass()
