**Changelog**

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
