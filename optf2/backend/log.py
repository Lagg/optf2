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

main_handler = logging.FileHandler(os.path.join(config.ini.get("resources", "cache-dir"), "op.log"))
path_formatter = logging.Formatter("%(asctime)-15s %(name)-5s %(levelname)-8s %(path)s - %(message)s",
                                   datefmt = "%m/%d %H:%M:%S")
main = logging.getLogger(config.ini.get("misc", "project-name"))

main_handler.setFormatter(path_formatter)

main.setLevel(logging.ERROR)
main.addFilter(webFilter())
main.addHandler(main_handler)
