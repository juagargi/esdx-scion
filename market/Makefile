.PHONY: protobuf, test, integration

protobuf:
	@./tools/make_protobuf.sh

test:
	@./manage.py test --parallel -v 0 market

integration:
	@./tools/integration_tests.sh
