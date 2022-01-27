**Changelog**

0.3
^^^
Thursday Jan 27 2022

* This version has been tested and requires revisions:

  * to verify ceph-osd units: **cs:ceph-osd-315** (`stable/21.10`, or `charmhub rev 511 or higher`)
  * to verify ceph-mon units: **cs:ceph-mon-61** (`stable/21.10`, or `charmhub rev 71 or higher`)
  * to verify nova-compute units: **cs:nova-compute-337** (`stable/21.10`, or `charmhub rev 449 or higher`)
  * to verify neutron-gateway units: **cs:neutron-gateway** (`stable/21.10`, or `charmhub rev 487`)

* Testing

  * Lint: Add black and isort
  * Functests: nova-compute and neutron-gateway tests run on the same model. Fix neutron-gateway routers/networks order.
  * Github actions: new PR workflow. lint-unit-docs-build on PR, full tests on approval and commands (`recheck-snap`, `recheck-full`).
  * Makefile: add `docs` and `format-code` targets

* Design, base verifier

  * Replace aggregate_results with check_executor (callable, catches common exceptions)
  * Check min Juju version required
  * Add `__bool__` function to the Result class
  * Add `--stop-on-failure` flag. Hard stop instead of waiting for other checks to finish.
  * Improve caching
  * Improve logging in CLI, defining different log levels for `libjuju` and `juju_verify`.
  * Add support to check units from multiple charms

* Verifiers

  * Nova-compute: uses `juju.machine.Machine.hostname` instead of a dedicated action
  * Neutron-gateway: align action calls to the charm action names.
  * Ceph-mon: fix `check_quorum`
  * Ceph-osd: fix AZ calculation method. The verifier now supports replication (not EC) by host, rack and row. Juju-run is required for some of the checks (replication rule) until we get Juju actions into the next stable release for the same purpose.

* Docs

  * add contributor guide, document limitations and known issues
  * add diagrams to verifiers documentation, as well as examples of results.

0.2.2
^^^^^
Monday Jul 12 2021

* This version has been tested and requires revisions:

  * to verify ceph-osd units: **cs:~/rgildein/ceph-osd-0** and **cs:~/rgildein/ceph-mon-3**
  * to verify ceph-mon units: **cs:~/rgildein/ceph-mon-3**
  * to verify nova-compute units: **cs:~openstack-charmers-next/nova-compute-562**
  * to verify neutron-gateway units: **cs:~/martin-kalcok/neutron-gateway-2**

0.2.1
^^^^^
Tuesday June 29 2021

* Move Git repo and CI/CD workflows to GitHub
* Create this changelog

0.2
^^^
Thursday June 10 2021

* Verify the Ceph cluster health (`LP#1917596`_)
* Verify the ceph-osd replication (`LP#1917599`_)
* Verify other ceph-osd units (`LP#1917600`_)
* Verify if one or more ceph-mon units can get shut down or rebooted (`LP#1917690`_)
* CephOsd.get_ceph_mon_units returns map with related units (`LP#1920131`_)
* CephOsd: verify the unit that is not in active workload (`LP#1921328`_)
* [run_action_on_units] cache usage to prevent re-execution (`LP#1922088`_)
* Reformat juju-verify output (`LP#1924974`_)
* Releases to pypi.org fail because of a direct dep (zaza) (`LP#1928938`_)

0.1
^^^
Wednesday May 12 2021

* Create the structure of the charm and unit tests (`LP#1915387`_)
* multiple `--units` or ` --machines` arguments are ignored (`LP#1920914`_)
* Enable targeting juju machines (`LP#1915728`_)
* Remove restrictions from BaseVerifier.run_action_on_units (`LP#1921505`_)
* Verify units/machines running inside another machine (`LP#1915806`_)
* README is outdated (`LP#1916724`_)
* nova-compute verifier: filter by status and state (`LP#1916593`_)
* Verify a nova-compute unit can be safely shut down (or rebooted) (`LP#1913700`_)
* Create a snapcraft.yaml file and attach the master repo to the snap CD system (build+publish to edge) (`LP#1915782`_)


.. _LP#1921505: https://bugs.launchpad.net/juju-verify/+bug/1921505
.. _LP#1917596: https://bugs.launchpad.net/juju-verify/+bug/1917596
.. _LP#1917599: https://bugs.launchpad.net/juju-verify/+bug/1917599
.. _LP#1917600: https://bugs.launchpad.net/juju-verify/+bug/1917600
.. _LP#1917690: https://bugs.launchpad.net/juju-verify/+bug/1917690
.. _LP#1920131: https://bugs.launchpad.net/juju-verify/+bug/1920131
.. _LP#1921328: https://bugs.launchpad.net/juju-verify/+bug/1921328
.. _LP#1928938: https://bugs.launchpad.net/juju-verify/+bug/1928938
.. _LP#1916724: https://bugs.launchpad.net/juju-verify/+bug/1916724
.. _LP#1920914: https://bugs.launchpad.net/juju-verify/+bug/1920914
.. _LP#1915387: https://bugs.launchpad.net/juju-verify/+bug/1915387
.. _LP#1915728: https://bugs.launchpad.net/juju-verify/+bug/1915728
.. _LP#1922088: https://bugs.launchpad.net/juju-verify/+bug/1922088
.. _LP#1915806: https://bugs.launchpad.net/juju-verify/+bug/1915806
.. _LP#1916593: https://bugs.launchpad.net/juju-verify/+bug/1916593
.. _LP#1924974: https://bugs.launchpad.net/juju-verify/+bug/1924974
.. _LP#1913700: https://bugs.launchpad.net/juju-verify/+bug/1913700
.. _LP#1915782: https://bugs.launchpad.net/juju-verify/+bug/1915782
