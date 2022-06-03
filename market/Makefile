.PHONY: protobuf, test, integration

protobuf:
	@./tools/make_protobuf.sh

test:
	@./manage.py test --parallel auto -v 0 market || \
		( echo; echo "----------------------- Repeating single process: ----------------" ; \
		./manage.py test market )

integration:
	@./tools/integration_tests.sh
