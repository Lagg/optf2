import ConfigParser
import os, sys

config_path = os.environ.get("OPTF2_CONFIG_PATH", "config.ini")

if not os.path.exists(config_path):
    sys.stderr.write("Config file {0} missing\n".format(config_path))
    raise SystemExit

ini = ConfigParser.SafeConfigParser()
ini.read(config_path)
