import os
import logging
import web

import config

class pathFilter(logging.Filter):
    def filter(self, record):
        try:
            record.path = web.ctx.path
        except AttributeError:
            record.path = "/"
        return True

main_handler = logging.FileHandler(os.path.join(config.ini.get("resources", "cache-dir"), "op.log"))
path_formatter = logging.Formatter("%(asctime)s %(name)s: %(levelname)s: %(path)s - %(message)s")
main = logging.getLogger(config.ini.get("misc", "project-name"))

main_handler.setFormatter(path_formatter)

main.setLevel(logging.ERROR)
main.addFilter(pathFilter())
main.addHandler(main_handler)
