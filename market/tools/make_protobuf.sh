#!/bin/bash

BASE=$(dirname "$0")


# python -m grpc_tools.protoc --proto_path=./ --python_out=./ --grpc_python_out=./ ./account.proto
cd "${BASE}/../market/"
python -m grpc_tools.protoc --proto_path=../proto/ --python_out=./ --grpc_python_out=./ ../proto/market.proto
