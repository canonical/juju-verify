Getting Started
===============

This section provides information on how to install and use ``juju-verify``.

Installing
----------

``juju-verify`` tool can be installed on various platforms via ``pip`` or
``snap``. It is tested and supported on amd64 but should work on other
platforms as well.

python package
^^^^^^^^^^^^^^

The python package can be installed using ``pip``:

::

  pip install juju-verify

.. seealso::
  More information can be found here `pypi.org`_.

snap
^^^^

The Snap package can be installed using the command:

::

  snap install juju-verify

.. seealso::
  More information can be found here `snapcraft`_.

How to use
----------

In this section, we will go through all CLI arguments, as well as the list
of supported checks and charms. Several usage examples have been included.

Description of CLI
^^^^^^^^^^^^^^^^^^

After successfully installing ``juju-verify``, help instructions can be
displayed using this command::

  $ juju-verify --help
  usage: juju-verify [-h] [--model MODEL] [-l {trace,debug,info}]
                   (--units UNITS [UNITS ...] | --machines MACHINES [MACHINES ...])
                   {shutdown,reboot}

  Verify that it's safe to perform selected action on specified units

  positional arguments:
    {shutdown,reboot}     Check to verify.

  optional arguments:
    -h, --help            show this help message and exit
    --model MODEL, -m MODEL
                          Connect to specific model.
    -l {trace,debug,info}, --log-level {trace,debug,info}
                          Set amount of displayed information
    --units UNITS [UNITS ...], -u UNITS [UNITS ...]
                          Units to check.
    --machines MACHINES [MACHINES ...], -M MACHINES [MACHINES ...]
                          Check all units on the machine.

checks
""""""

There are currently only two supported checks

* shutdown
* reboot

which will provide the user with information about the safe removal of the
units/machines.

charms
""""""

At the same time, both checks are implemented for the following charms:

* nova-compute
* ceph-osd

.. seealso::

  For more information about which checks are run for each charms visit this
  page.

.. todo:: add link to verifiers.rts document

units/machines
""""""""""""""

Multiple values can be passed to the ``--units`` and ``--machines`` arguments.
There are two ways of using them:

::

  juju-verify reboot --units ceph-osd/0 ceph-osd/1
  # or
  juju-verify reboot --units ceph-osd/0 --units ceph-osd/1

Usage examples
^^^^^^^^^^^^^^

ceph-osd units verification
"""""""""""""""""""""""""""

The following example consists of 3 ceph-osd units and 3 ceph-mon units. The
Ceph cluster replication factor across all pools is 3 (size=3, min_size=2).
This means that the cluster will be degraded when less than 3 copies of a PG
exist, and it will stop accepting R/W when less than 2 copies of a PG exist.

Let's see what ``juju-verify`` tells us to reboot one ceph-osd unit.

::

  $ juju-verify reboot -u ceph-osd/0
  Result: OK
  Reason: ceph-mon/1: Ceph cluster is healthy

However, if we try to reboot two units instead of one, the check should fail.
This is because when two units are removed, only one will remain and at least
two are needed.

::

  $ juju-verify reboot -u ceph-osd/0 -u ceph-osd/1
  Result: FAIL
  Reason: ceph-mon/2: Ceph cluster is healthy
  The minimum number of replicas in 'ceph-osd' is 1 and it's not safe to restart/shutdown 2 units. 0 units are not active.

.. _pypi.org: https://pypi.org/project/juju-verify/
.. _snapcraft: https://snapcraft.io/about
