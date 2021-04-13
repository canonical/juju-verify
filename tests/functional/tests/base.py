"""Generic setup for functional tests."""

import unittest

from juju import loop
import zaza.model

from juju_verify import juju_verify


class BaseTestCase(unittest.TestCase):
    """Base class for functional testing of verifiers."""

    @classmethod
    def setUpClass(cls):
        """Run class setup for running tests."""
        super(BaseTestCase, cls).setUpClass()
        cls.log_level = 'info'
        cls.check = 'shutdown'
        juju_verify.config_logger(cls.log_level)
        cls.model = loop.run(juju_verify.connect_model(zaza.model.CURRENT_MODEL))
