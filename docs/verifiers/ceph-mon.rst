Ceph-mon verifier
=================

So far, the "reboot" and "shutdown" actions are supported and they both
perform the same set of checks.

* check minimum Juju version
* check Ceph Monitor quorum
* check Ceph clusters health


check Juju version
------------------

Ceph-mon verification relies on Juju features introduced in 2.8.10. If this minimum
version requirement is not met, the verification will stop and return ``Failed`` result
immediately.

check Ceph Monitor quorum
-------------------------

This check verifies that intended action won't remove more than half of monitors in each
affected ceph-mon cluster. Majority of Ceph monitors must be kept alive after the change
to maintain quorum.

check Ceph clusters health
--------------------------

This check runs ``get-health`` action on one of the targeted ``ceph-mon`` units to get
cluster's health. If targeted units belong to multiple Juju applications, ``get-health``
action is run on one unit per application. A cluster is considered healthy if the
action's output contains HEALTH_OK. All affected clusters must be healthy for
verification to succeed.
