"""Collection of juju verification exceptions"""


class VerificationError(Exception):
    """Exception related to the main verification process."""


class CharmException(Exception):
    """Exception related to the charm or the unit that runs it."""
