import socket, web, os

# See steamodd for supported modes
game_modes = {"p2": "Portal 2",
              "tf2b": "Team Fortress 2 Beta",
              "tf2": "Team Fortress 2",
              "d2": "DOTA 2"}

# You probably want this to be
# an absolute path if you're not running the built-in server
template_dir = "templates/"

# Most links to other viewer pages will
# be prefixed with this.
virtual_root = "/"

# The url to prefix URLs
# pointing to static data with
# e.g. class icons
static_prefix = "/static/"

api_key = None

# It would be nice of you not to change these
project_name = "OPTF2"

# Refresh cache every x seconds.
cache_pack_refresh_interval = 30

# The absolute minimum time between
# schema cache refreshes in seconds.
cache_schema_grace_time = 30

# How many rows to show for the top viewed backpacks table
top_backpack_rows = 10

# Turn on debugging (prints a backtrace and other info
# instead of returning an internal server error)
web.config.debug = False

# Enables fastcgi support with flup, be sure to have it
# installed.
enable_fastcgi = False

# These stop the script name from showing up
# in URLs after a redirect. Remove them
# if they cause problems.
os.environ["SCRIPT_NAME"] = ''
os.environ["REAL_SCRIPT_NAME"] = ''

# The cache directory, this will
# have sensitive data in it that
# shouldn't be publicly accessible

cache_file_dir = "/tmp/opnet-cache"

if not os.path.exists(cache_file_dir):
    os.makedirs(cache_file_dir)

# Used as a timeout for fetching external data
socket.setdefaulttimeout(2)

web.config.session_parameters["timeout"] = 86400
web.config.session_parameters["cookie_name"] = "optf2_session_id"

# A list of valid ISO language codes
valid_languages = ["da", "nl", "en", "fi", "fr", "de", "it", "ja",
                   "ko", "no", "pl", "pt", "ru", "zh", "es", "sv"]

wiki_mapping = {"p2": ("Portal Wiki", "http://theportalwiki.com/wiki/"),
                "tf2": ("Official TF Wiki", "http://wiki.teamfortress.com/wiki/"),
                "d2": ("DOTA Wiki", "http://dota2wiki.com/wiki/")}
wiki_mapping["tf2b"] = wiki_mapping["tf2"]

# The 64 bit ID of the Valve group (this is how I check
# if the user is a Valve employee)
valve_group_id = 103582791429521412
