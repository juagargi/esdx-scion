.PHONY: all protobuf

all:


protobuf:
	@cd market && protoc --go_out=. --go_opt=paths=source_relative --go-grpc_out=. --go-grpc_opt=paths=source_relative -I ../../esdx4ixps/proto/ ../../esdx4ixps/proto/market.proto
