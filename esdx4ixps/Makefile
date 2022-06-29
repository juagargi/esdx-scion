.PHONY: protobuf, test, integration

protobuf:
	@./tools/make_protobuf.sh

test: test_market test_reloader

test_market:
	@./manage.py test --parallel -v 0 market

test_reloader:
	@# @python -m pytest -q ./reloader/tests/test_*.py
	@pytest -q ./reloader/ $(args)  # e.g. call `make test_reloader args=-s` to display the output

integration:
	@./tools/integration_tests.sh

migration_replace:
	@rm market/migrations/0001_initial.py
	@./manage.py makemigrations market
