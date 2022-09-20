# Contributor Guide

This library is open source and under the ([GNU General Public License v3.0][LICENSE]),
which will cover any contributions you may make to this project.
If you're interested in contributing to the ``juju-verify`` code or documentation,
the following will help you get started. Please familiarise yourself with the terms of
the license and read this page before start working on any contributions.

## Python version

This tool has been supported since Python version 3.6.

## Code of conduct

We have adopted the [Ubuntu Code of Conduct][COC].

## Releases and versions

Juju-verify uses semantic versioning three-part version number, where the numbers
describe:

1. major - this represents a major change in the logic of the code or add a new whole
           e.g. support for kubernetes verifiers
2. minor - will increase when a new verifier becomes available or the base verification
           logic of any verifiers changes
3. path - if a new check is added or modified, but the base logic does not change

The version should not be increased if there is any change in the documentation and
in the lint, unit or functional tests.

## How to contribute

Is your favorite charm missing from the list of supported charm? Don't hesitate
to add it. This plugin is easily extensible.

All you need to do is create new class in `juju_verify.verifiers` package that
inherits from `juju_verify.verifiers.BaseVerifier` (see the class documentation for
more details) and implement the necessary logic. When you're finished all the checks,
use `check_executor` to execute them. This executor wraps your checks and provides
a default output, if non returned, and catch a list of errors.

Then, the charm name needs to be added to `SUPPORTED_CHARMS` dictionary in
`juju_verify/verifiers/__init__.py` *et voilà*, the charm is now supported.

Don't forget to add unit tests and run them together with the lint test using
the command:

```bash
make test
```
If you are adding new verifiers, consider adding functional tests or report a bug
with a good description of how to perform these functional tests. In other words,
explain the logic of the checks well.

If you are modifying the logic of any check or adding a new one, consider adding this
new approach to existing functional tests.

Functional tests require some applications to use a VIP. Please ensure the `OS_VIP00`
environment variable is set to a suitable VIP address before running functional tests.

### Developer workflow

The workflow for contributing code is as follows:

1. [Submit a bug][bugs] to explain the need for and track the change.
2. Create a branch on your fork of the repo with your changes, including a unit
   test covering the new or modified code. Functional tests are not mandatory, but
   it is preferred to have them.
3. Submit a PR. The PR description should include a link to the bug on Launchpad.
4. Update the Launchpad bug to include a link to the PR and the `review-needed` tag.
5. Once reviewed and merged into the master branch, the change will become available at
   the edge channel in **snapcraft**.
6. Stable release is performed after tagging the master branch and merging it into
   the stable branch.

### Pull Request workflow

The basic idea of the life cycle of contributing and Pull Request is shown in
the following diagram.

![Pull Request workflow diagram](img/pr-workflow.svg)

### Checks and checks_executor

Each check must be run using the `checks_executor` function. This function accepts
arguments as checks as a called function that is executed in a try/except with list
of exceptions. Each error from the exception list is captured and returned as a check
failure `Result(FAIL, f"{check.__name__} check failed with error: {error}")`, but not
as a whole juju-verify failure. If the performed check does not return any output,
the `Result(OK, "<check .__ name __> check successful")` form is used.

## Lint, unit and functional tests

### Lint tests

For purpose of a lint test we are using `flake8`, `mypy` and `pylint` and could be
executed be running:

```bash
make lint
# or
tox -e lint
```

To find out what's actually running you can look in `tox.ini`, specifically on
"testenv:lint". The configuration for `flake8` could be found in `tox.ini` and for
`mypy` in `mypy.ini`.

### Unit tests

For unit tests we use `pytests` with a strict rule of 100% coverage. Unit tests must
be runnable on Python versions 3.6, 3.7, 3.8 and 3.9. To perform unit tests you can use
this command:

```bash
make unittest
# or
tox -e unit
```

To find out what's actually running you can look in `tox.ini`, specifically on
"testenv" and configuration can be found in `pytest.ini`.

Example of unit tests:

```python
def test_verify_ceph_mon_shutdown(mocker):
    """Test that verify_shutdown links to verify_reboot."""
    mocker.patch.object(CephMon, "verify_reboot")
    unit = Unit("ceph-mon/0", Model())
    verifier = CephMon([unit])
    verifier.verify_shutdown()
    verifier.verify_reboot.assert_called_once()
```

This example show how to test the `verify_shutdown` function in the `CephMon` class.
Function `verify_shutdown` is in fact only a symbolic reference to funkciu
`verify_reboot` and we need to test whaether this function was called.


### Functional tests

The function tests are runs by [zaza][zaza]. These tests must be configured in
`tests/functional/tests.yaml`, where you need to add tests in the tests section
and define a bundle for these tests in gate_bundles section.

To create functional tests for `nova-compute` charm, you need to add a budnle to the
`tests/functional/bundles` directory. name of this bundle should correspond to the name
of the charm or a bundle of which this charm is a part. E.g. `nova-compute` is part of
the `openstack-base` bundle. The last step is to add the Python file that contains the
tests to `tests/functional/tests/` directory.

```bash
make functional
# or
tox -e func
```

To find out what's actually running you can look in `tox.ini`, specifically on
"testenv:func".

**NOTE:** If you want to run functional tests in debug mode, you can use the
`tox -e func-debug`, which will provide more logs and models will not be destroyed.
This can be used to create functional tests, where you can then test them on this model.

Example of unit functional tests:

```python
class CephTests(BaseTestCase):
    def test_single_osd_unit(self):
        """Test that shutdown of a single unit returns OK."""
        # juju-verify shutdown --units ceph-osd/1

        units = ['ceph-osd/0']
        check = 'shutdown'
        unit_objects = loop.run(juju_verify.find_units(self.model, units))
        verifier = get_verifier(unit_objects)
        result = verifier.verify(check)
        logger.info("result: %s", result)
        self.assertTrue(result.success)
```

This is a test that simulates the CLI call `juju-verify shutdown --units ceph-osd/1`
on a healthy CEPH cluster, which should end with an OK result.


## Documentation

The latest documentation for this project could be found in the
[juju-verify.readthedocs.io][readthedocs].


<!-- Links -->
[LICENSE]: https://github.com/canonical/juju-verify/blob/master/LICENSE
[COC]: https://ubuntu.com/community/code-of-conduct
[bugs]: https://bugs.launchpad.net/juju-verify/+filebug
[readthedocs]: https://juju-verify.readthedocs.io/en/latest/index.html
[zaza]: https://zaza.readthedocs.io/en/latest/
