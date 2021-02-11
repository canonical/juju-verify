help:
	@echo "This project supports the following targets"
	@echo ""
	@echo " make help - show this text"
	@echo " make lint - run flake8 and mypy"
	@echo " make test - run the lint and unittest targets"
	@echo " make unittest - run the tests defined in tests/unit/ subdirectory"
	@echo " make release - build juju-verify and give hints to release it"
	@echo " make clean - remove unneeded files"
	@echo ""

lint:
	@echo "Running flake8 and mypy"
	@tox -e lint

test: lint unittest

unittest:
	@tox -e unit

release: clean
	@echo "Release procedure not yet supported"

clean:
	@echo "Cleaning files"
	@git clean -fxd

# The targets below don't depend on a file
.PHONY: lint test unittest release clean help
