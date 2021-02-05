"""Juju 'verify' plugin that allows user to check whether it's safe to execute
actions like 'stop' or 'reboot' on juju units without affecting availability
and integrity
"""
from .juju_verify import main
