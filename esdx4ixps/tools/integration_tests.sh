#!/bin/bash

BASE=$(realpath `dirname $0`/..)

if [ -f db.sqlite3 ]; then
    tempdir=`mktemp -d`
    mv db.sqlite3 $tempdir
fi

cd "$BASE"

"${BASE}/integration_test.py"
RET=$?

if [ -n "$tempdir" ]; then
    mv "$tempdir"/db.sqlite3 .
    rmdir "$tempdir"
fi

exit $RET
