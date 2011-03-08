#!/usr/bin/env python

# Run this script to initialize optf2's database

import config
from openid.store import sqlstore

schema = file("schema.sql").read().split(';')

for query in schema:
    query = query.strip().strip('\n')
    if query:
        print(query)
        config.database_obj.query(query)

try:
    sqlstore.MySQLStore(config.database_obj._db_cursor().connection).createTables()
except:
    print("OpenID Tables may already be created")
