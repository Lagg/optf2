import ConfigParser
import os, sys

config_path = os.environ.get("OPTF2_CONFIG_PATH", "config.ini")

if not os.path.exists(config_path):
    sys.stderr.write("Config file {0} missing\n".format(config_path))
    raise SystemExit

class OPConfig(ConfigParser.SafeConfigParser):
    def __init__(self, *args, **kwargs):
        ConfigParser.SafeConfigParser.__init__(self, *args, **kwargs)

    def getlist(self, section, option):
        if self.has_option(section, option):
            listval = self.get(section, option)
        else:
            return []

        return map(str.strip, listval.split(','))

ini = OPConfig()
ini.read(config_path)
