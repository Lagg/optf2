import os
import logging
import web

import config

class webFilter(logging.Filter):
    def filter(self, record):
        try:
            record.path = web.ctx.path
        except AttributeError:
            record.path = "/"

        return True

cachedir = config.ini.get("resources", "cache-dir")

try:
    os.makedirs(cachedir)
except OSError:
    pass

main = logging.getLogger(config.ini.get("misc", "project-name"))
main.addHandler(logging.NullHandler())
