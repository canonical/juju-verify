"""Generic setup for functional tests."""

import unittest

from juju import loop
import zaza.model

from juju_verify import juju_verify


class BaseTestCase(unittest.TestCase):
    """Base class for functional testing of verifiers."""

    def __init__(self):
        """Set basic generic items for all tests."""
        super().__init__()
        self.log_level = 'info'
        self.check = 'shutdown'
        juju_verify.config_logger(self.log_level)
        self.model = loop.run(juju_verify.connect_model(zaza.model.CURRENT_MODEL))
