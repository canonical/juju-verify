Ceph-mon verifier
=================

So far, the "reboot" and "shutdown" actions are supported and they both
perform the same set of checks.

* check minimum Juju version
* check Ceph Monitor quorum
* check Ceph clusters health

::

  $ juju-verify reboot --unit ceph-mon/0
  Checks:
  [OK] check_affected_machines check passed
  [OK] check_has_sub_machines check passed
  [OK] Minimum juju version check passed.
  [OK] Ceph-mon quorum check passed.
  [OK] ceph-mon/0: Ceph cluster is healthy

  Overall result: OK (All checks passed)


check Juju version
------------------

Ceph-mon verification relies on Juju features introduced in 2.8.10. If this minimum
version requirement is not met, the verification will stop and return ``Failed`` result
immediately. So it works as if the juju-verify was run with the ``--stop-on-failure``
flag.

Example of response when check failed, due to Juju client version 2.7.5:

::

  [FAIL] Juju agent on unit ceph-mon/0 has lower than minimum required version. 2.7.5 < 2.8.10

on the contrary, if the client is met the minimum version:

::

  [OK] Minimum juju version check passed.


check Ceph Monitor quorum
-------------------------

This check verifies that intended action won't remove more than half of monitors in each
affected Ceph cluster. Majority of Ceph monitors must be kept alive after the change to
maintain quorum.

If the restart/shutdown of the ceph-mon unit(s) from the Ceph cluster does not endanger
the monitoring quorum, the following message is displayed:

::

  [OK] Ceph-mon quorum check passed.

and vice versa if restart/shutdown the unit(s) causes a loss of Ceph quorum:

::

  [FAIL] Removing unit ceph-mon/0 will lose Ceph mon quorum

Another possible failure is if it is not possible to read the result from the output of
the "get-quorum-status" action. In this case, the following result message will be
present along with the action ID.

::

  [FAIL] Failed to parse quorum status from action 24.


check Ceph clusters health
--------------------------

This check runs ``get-health`` action on one of the targeted ``ceph-mon`` units to get
cluster's health. If targeted units belong to multiple Juju applications, ``get-health``
action is run on one unit per application. A cluster is considered healthy if the
action's output contains ``HEALTH_OK``. All affected clusters must be healthy for
verification to succeed.

The successful result message should look like this:

::

  [OK] ceph-mon/1: Ceph cluster is healthy


On the other hand, the check fails if the output does not contain ``HEALTH_OK``. A CEPH
cluster will be marked as unhealthy if the output contains ``HEALTH_WARN`` or
``HEALTH_ERR``, and in an unknown state if it does not contain any of the above
expressions.

::

  [FAIL] ceph-mon/1: Ceph cluster is unhealthy

There are several possible reasons why the CEPH cluster is not healthy, but not all of
them can be listed here. For more info visit `ceph-monitoring`_.

To see details run juju-verify in debug mode. Bellow is an example of a log message
that provide more information about why CEPH cluster is unhealthy.

::

  | DEBUG | Unit (ceph-mon/1): Ceph cluster health 'HEALTH_WARN Degraded data redundancy: 8 pgs undersized; too few PGs per OSD (8 < min 30)'


.. _ceph-monitoring: https://docs.ceph.com/en/pacific/rados/operations/monitoring/
