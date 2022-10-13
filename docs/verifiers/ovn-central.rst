OVN-central verifier
=====================

The "reboot" and "shutdown" actions are supported for ovn-central verifier. "reboot"
action refers to temporary bringing down unit for maintenance with the intention of
bringing it back on. A "shutdown" action refers to permanently removing unit from the
cluster. Both actions have set of common checks meant to asses cluster integrity and then
specialized checks that verify impact of given action on the cluster. Successfully
passing the common tests is a prerequisite for execution of specialized checks. If any of
the common checks fail, the execution of verifier will be halted and user will be
presented with result describing failures of the common checks.

Common checks:

* check supported charm version
* check single application
* check leader consistency
* check uncommitted logs
* check unknown servers

Reboot checks:

* check reboot

Shutdown checks:

* check downscale


Example of reboot action and output:

::

  $ juju-verify reboot --unit ovn-central/0
  ===[ovn-central/0]===
  Checks:
  [OK] check_affected_machines check passed
  [OK] check_has_sub_machines check passed
  [OK] Charm supports all required actions.
  [OK] Selected units are part of only one application.
  [OK] All units agree that fd42 is Southbound leader.
  [OK] All units agree that 6053 is Northbound leader.
  [OK] ovn-central/1 (Northbound leader) reports 0 uncommitted log entries.
  [OK] ovn-central/2 (Southbound leader) reports 0 uncommitted log entries.
  [OK] No disassociated cluster members reported.
  [OK] OVN cluster with 5 units can safely tolerate simultaneous reboot of 1 units.

  Result: OK (All checks passed)


Example of shutdown action and output:

::

  $ juju-verify shutdown --unit ovn-central/0
  ===[ovn-central/0]===
  Checks:
  [OK] check_affected_machines check passed
  [OK] check_has_sub_machines check passed
  [OK] Charm supports all required actions.
  [OK] Selected units are part of only one application.
  [OK] All units agree that fd42 is Southbound leader.
  [OK] All units agree that 6053 is Northbound leader.
  [OK] ovn-central/1 (Northbound leader) reports 0 uncommitted log entries.
  [OK] ovn-central/2 (Southbound leader) reports 0 uncommitted log entries.
  [OK] No disassociated cluster members reported.
  [OK] Removing 1 units from cluster of 6 won't impact its fault tolerance.

  Result: OK (All checks passed)

supported charm version
-----------------------

This verifier requires that the ovn-central unit supports "cluster-status" action. In
case it does not, it will be necessary to upgrade the charm in order to use this
verifier.

Successfully passing test will display following message in the result:

::

  [OK] Charm supports all required actions.

Failing the test will show this message instead:

::

  [FAIL] Charm does not support required action 'cluster-status'. Please try upgrading charm.


check single application
------------------------

At the moment this verifier can handle only units belonging to the same application and
therefore to the same cluster. This check verifies that every unit targeted by
the verifier is member of the same application.

Even though the `juju-verify` as a whole does not currently support verifying multiple
applications, this check is added on top in case the future improvements to `juju-verify`
will add this functionality.

Successfully passing test will display following message in the result:

::

  [OK] Selected units are part of only one application.

In case that user supplied units from multiple applications, following error will
be shown in the final result:

::

  [FAIL] Can't verify multiple ovn-central application at the same time. Currently selected units belong to: ovn-cluster-1, ovn-cluster-2"


check leader consistency
------------------------

This check verifies that every unit agrees on who is the leader in both Southbound and
Northbound OVN clusters. Discrepancy in opinion on leadership indicates split
brain/cluster failure which should be fixed before further operations can proceed.

Example of successful result of this check:

::

  [OK] All units agree that fd42 is Southbound leader.
  [OK] All units agree that 6053 is Northbound leader.

In case that cluster members in any unit disagree on who is the leader, error like this
will be shown in the final result:

::

  [FAIL] There's no consensus on Southbound cluster leader. f48d is supported by ovn-central/0, ovn-central/2; 6899 is supported by ovn-central/1;


check uncommitted logs
----------------------

This check verifies that all the updates (log entries) from the cluster leaders, both
Southbound and Northbound, were distributed to followers and it's guaranteed that the
followers will apply these updates. Uncommitted entries indicate problems in the cluster
that prevent leader to from communicating with followers and keeping the cluster
information consistent. User must remedy this situation before it can be recommended
to proceed with rebooting members or downscaling of the cluster.

Example of successful result of this check:

::

  [OK] ovn-central/2 (Southbound leader) reports 0 uncommitted log entries
  [OK] ovn-central/1 (Northbound leader) reports 0 uncommitted log entries.

If any leader reports uncommitted entries, error message like this will be shown in the
final result:

::

  [FAIL] ovn-central/1 (Northbound leader) reports 2 uncommitted log entries.


check unknown servers
---------------------

This check verifies that no "unknown" servers are listed in the cluster status. Unknown
server is an OVN cluster (Southbound or Northbound) member that is not associated with
any running unit but still shows up in output of cluster status. This can happen when
unit is abruptly removed and it fails to gracefully leave the cluster. Such servers can
be removed using "cluster-kick" action on one of the remaining ovn-central units.

Successfully passing test will display following message in the result:

::

  [OK] No disassociated cluster members reported.

Failing this check will display message like this:

::

  [FAIL] Southbound cluster reports servers that are not associated with a unit.


check reboot
------------

This check assesses the impact of temporary bringing down selected units on the cluster.
Number of selected units must be smaller or equal to the cluster's fault tolerance for
this test to pass. OVN cluster is using Raft protocol to maintain consistent cluster. For
the consistency to be maintained, cluster must have minimum quorum of

::

  ( N // 2 ) + 1

members where "N" is total number of members registered in the cluster. Fault tolerance
is then calculated as

::

  N  - min_quorum

If the number of rebooted units is smaller than the maximum fault
tolerance this check will pass with following (example) message in the final result:

::

  [OK] OVN cluster with 5 units can safely tolerate simultaneous reboot of 1 units.


If the number of rebooted units is equal to the maximum cluster fault tolerance, the test
will also pass but following warning will also be included in the final result:

::

  [WARN] While the rebooted units are down, this cluster won't be able to tolerate any more failures.

If the number of rebooted units would bring cluster below minimum required quorum, this
check will fail with following (example) message in the result:

::

  [FAIL] OVN cluster with 3 units can not tolerate simultaneous reboot of 2 units.


check downscale
---------------

This check assesses an impact of permanently downscaling a cluster on its fault
tolerance. If the fault tolerance is unaffected, for example downscaling from 4 units to
3 ( fault tolerance remains 1 ), this check will pass with following message

::

  [OK] Removing 1 units from cluster of 4 won't impact its fault tolerance.

If the fault tolerance is decreased, for example downscaling from 5 units to 3 ( fault
tolerance is decreased from 2 to 1 ), this check passes but displays warning to the user.

::

  [WARN] Removing 2 units from cluster of 5 will decrease its fault tolerance from 2 to 1.

And if the requested change would bring the cluster's fault tolerance to 0, for example
downscaling from 5 to 2 units, this check will fail with following message:

::

  [FAIL] Removing 3 units from cluster of 5 would bring its fault tolerance to 0.