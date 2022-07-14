#!/bin/bash

if (($# < 1)); then
    echo -e "bad usage:\n$0 IA"
    exit 1
fi
IA="$1"
IAfile=$(echo "$IA" | tr ':' '_')

# store in PKCS#8 ("BEGIN PRIVATE KEY"), allows to define the algorithm (always RSA for now)
openssl req -newkey rsa:4096 \
            -x509 \
            -sha256 \
            -days 3650 \
            -nodes \
            -out "${IAfile}.crt" \
            -keyout "${IAfile}.key" \
            -subj "/C=CH/O=Netsec/OU=ETH/CN=$IA"
