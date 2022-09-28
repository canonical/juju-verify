help:
	@echo "This project supports the following targets"
	@echo ""
	@echo " make help - show this text"
	@echo " make dev-environment - setup the development environment"
	@echo " make pre-commit - run pre-commit checks on all the files"
	@echo " make lint - run flake8, mypy, pylint, black and isort"
	@echo " make format-code - run isort and black"
	@echo " make test - run the lint and unittest targets"
	@echo " make test-full - run the lint and unittest-full targets"
	@echo " make unittest - run the tests defined in tests/unit/ subdirectory"
	@echo " make unittest-full - run the tests defined in tests/unit/ subdirectory with python 3.6 and 3.8"
	@echo " make functional - run functional tests"
	@echo " make release - build juju-verify and give hints to release it"
	@echo " make clean - remove unneeded files"
	@echo " make snap - build juju-verify as a snap"
	@echo " make docs - build documentation"
	@echo ""

dev-environment:
	@echo "Creating virtualenv with pre-commit installed"
	@tox -r -e dev-environment

pre-commit:
	@tox -e pre-commit

lint:
	@echo "Running flake8, mypy, pylint, black and isort"
	@tox -e lint

format-code:
	@echo "Running isort and black"
	@tox -e reformat

unittest:
	@echo "Running unittest"
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
	@git clean -fxd -e '.idea/' -e '.vscode/'

functional:
	@echo "Executing functional tests"
	@tox -e func

docs:
	@echo "Build documentation"
	@tox -e docs

# The targets below don't depend on a file
.PHONY: docs lint test unittest release clean help build build-verify snap functional
