import socket, web, os
from openid.store import sqlstore
    
# You probably want this to be
# an absolute path if you're not running the built-in server
template_dir = "templates/"

# Most links to other viewer pages will
# be prefixed with this.
virtual_root = "/"

css_url = "/static/style.css"

# The url to prefix URLs
# pointing to static data with
# e.g. class icons
static_prefix = "/static/"

api_key = None

language = "en"

# It would be nice of you not to change these
project_name = "OPTF2"
project_homepage = "http://projects.optf2.com/projects/optf2"

# Cache a player's backpack. Reduces the number of API
# requests and makes it a lot faster but might make the
# database big
cache_pack = True

# Refresh cache every x seconds.
cache_pack_refresh_interval = 30

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

# The link to the news page/changelog
# set this to None if you don't want
# this shown. (Not recommended)
news_url = "http://agg.optf2.com/log/?cat=5"

# The max size of the backpack. Used
# for the padded cell sort
backpack_padded_size = 300

# The cache directory, this will
# have sensitive data in it that
# shouldn't be publicly accessible

cache_file_dir = "/tmp/steamodd"

# Used as a timeout for fetching external data
socket.setdefaulttimeout(5)

web.config.session_parameters["timeout"] = 86400
web.config.session_parameters["cookie_name"] = "optf2_session_id"

# Database parameters
database = {"username": "root",
            "password": "",
            "database": "optf2_dev",
            "host": "localhost"}

# Only tested with mysql, previously worked on sqlite but I don't recommend it.
database_obj = web.database(dbn = "mysql", db = database["database"], user = database["username"],
                            pw = database["password"], host = database["host"])
