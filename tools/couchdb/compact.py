# Compacts all database views and files
import sys
sys.path.append("../../")

import config

server = config.database_server

for db in server.all_dbs():
    if not db.startswith("_"):
        server[db].view_cleanup()
        server[db].compact()
