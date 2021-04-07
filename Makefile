help:
	@echo "This project supports the following targets"
	@echo ""
	@echo " make help - show this text"
	@echo " make lint - run flake8 and mypy"
	@echo " make test - run the lint and unittest targets"
	@echo " make unittest - run the tests defined in tests/unit/ subdirectory"
	@echo " make release - build juju-verify and give hints to release it"
	@echo " make clean - remove unneeded files"
	@echo " make snap - build juju-verify as a snap"
	@echo ""

lint:
	@echo "Running flake8 and mypy"
	@tox -e lint

unittest:
	@tox -e unit

test: lint unittest

build:
	@echo "Building python package"
	@tox -e build

build-verify:
	@echo "Verifying built python package"
	@tox -e build-verify

snap:
	@echo "Building snap from the python package"
	@snapcraft snap

release: clean build build-verify
	@echo "Release procedure not yet supported"
	@echo "Hint: twine upload dist/*"

clean:
	@echo "Cleaning files"
	@git clean -fxd -e '!.idea'

# The targets below don't depend on a file
.PHONY: lint test unittest release clean help build build-verify snap
