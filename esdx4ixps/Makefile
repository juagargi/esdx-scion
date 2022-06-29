.PHONY: protobuf, test, integration

protobuf:
	@./tools/make_protobuf.sh

test:
	@./manage.py test --parallel -v 0 market

integration:
	@./tools/integration_tests.sh

migration_replace:
	@rm market/migrations/0001_initial.py
	@./manage.py makemigrations market
