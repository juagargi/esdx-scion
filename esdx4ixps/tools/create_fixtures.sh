#!/bin/bash

# based on netsec-ethz/scionlab

# backup db
tempdir=`mktemp -d`
mv db.sqlite3 $tempdir

# init new db
python manage.py migrate -v 1

# create and dump data for fixture
python manage.py shell -c 'from market.fixtures.create_fixtures import create_fixtures; create_fixtures()'
python manage.py dumpdata --format=yaml market > market/fixtures/testdata.yaml

# get db back
mv $tempdir/db.sqlite3 .
