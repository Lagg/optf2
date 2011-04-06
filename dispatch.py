#!/usr/bin/env python

"""
Copyright (c) 2008-2011, Anthony Garcia <lagg@lavabit.com>

Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted, provided that the above
copyright notice and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
"""

try:
    import logging, traceback
    from openid.consumer import consumer
    from openid.store import sqlstore
    import hmac, hashlib
    import steam, os, json, urllib2
    import web
    import cPickle as pickle
    import time
    import config
    steam.set_api_key(config.api_key)
    from optf2.backend import database
    from optf2.backend import items as itemtools
    import optf2.frontend.markup as markuptools
except ImportError as E:
    print(str(E))
    raise SystemExit

urls = (
    config.virtual_root + "comp/(.+)", "user_completion",
    config.virtual_root + "user/(.*)", "pack_fetch",
    config.virtual_root + "feed/(.+)", "pack_feed",
    config.virtual_root + "item/(.+)", "pack_item",
    config.virtual_root + "persona/(.+)", "persona",
    config.virtual_root + "loadout/(.+)", "loadout",
    config.virtual_root + "attrib_dump", "attrib_dump",
    config.virtual_root + "schema_dump", "schema_dump",
    config.virtual_root + "about", "about",
    config.virtual_root + "openid", "openid_consume",
    config.virtual_root + "(.+)", "pack_fetch",
    config.virtual_root, "index"
    )

# The 64 bit ID of the Valve group (this is how I check
# if the user is a Valve employee)
valve_group_id = 103582791429521412

# These should stay explicit
render_globals = {"css_url": config.css_url,
                  "virtual_root": config.virtual_root,
                  "static_prefix": config.static_prefix,
                  "encode_url": web.urlquote,
                  "len": len,
                  "particledict": itemtools.particledict,
                  "instance": web.ctx,
                  "project_name": config.project_name,
                  "project_homepage": config.project_homepage,
                  "wiki_url": "http://wiki.teamfortress.com/wiki/",
                  "news_url": config.news_url,
                  "qurl": web.http.changequery,
                  "iurl": web.input,
                  "markup": markuptools
                  }

app = web.application(urls, globals())

def lang_hook():
    lang = web.input().get("lang")

    if lang not in config.valid_languages: lang = "en"
    web.ctx.language = lang

app.add_processor(web.loadhook(lang_hook))
templates = web.template.render(config.template_dir, base = "base",
                                globals = render_globals)

logging.basicConfig(filename = os.path.join(config.cache_file_dir, "optf2.log"), level = logging.DEBUG)

db_obj = config.database_obj

session = web.session.Session(app, web.session.DBStore(db_obj, "sessions"))

openid_secret = os.path.join(config.cache_file_dir, "oid_super_secret")
if not os.path.exists(openid_secret):
    secretfile = file(openid_secret, "wb+")
    secretfile.write(os.urandom(32))
    secretfile.close()
openid_secret = file(openid_secret, "rb").read()

def make_openid_hash(url):
    return hmac.new(openid_secret, url, hashlib.sha1).hexdigest()

def check_openid_hash(thehash):
    strs = thehash.split(',')
    if len(strs) == 2 and strs[0] == make_openid_hash(strs[1]):
        return True
    session.kill()
    return False

def openid_get_id():
    thehash = session.get("identity_hash")
    if thehash and check_openid_hash(thehash):
        hashurl = thehash.split(',')[1]
        if hashurl.endswith('/'): hashurl = hashurl[:-1]
        return database.load_profile_cached(os.path.basename(hashurl))
    return None
render_globals["get_openid"] = openid_get_id

def internalerror():
    logging.error(traceback.format_exc())
    return web.internalerror(templates.error("Unknown error, " + config.project_name + " may be down for maintenance"))
if not web.config.debug: app.internalerror = internalerror

class schema_dump:
    """ Dumps everything in the schema in a pretty way """

    def GET(self):
        try:
            query = web.input()
            items = list(database.load_schema_cached(web.ctx.language))
            filter_qualities = itemtools.get_present_qualities(items)

            try: items = itemtools.filter_by_class(items, query["sortclass"])
            except KeyError: pass
            try: items = itemtools.filter_by_quality(items, query["quality"])
            except KeyError: pass
            try: items = itemtools.sort(items, query["sort"])
            except KeyError: pass

            stats = itemtools.get_stats(items)
            filter_classes = itemtools.get_equippable_classes(items)

            return templates.schema_dump(itemtools.process_attributes(items), filter_classes, filter_qualities = filter_qualities, stats = stats)
        except:
            return templates.error("Couldn't load schema")

class loadout:
    """ User loadout lists """

    def GET(self, user):
        try:
            userp = database.load_profile_cached(user)
            items = database.load_pack_cached(userp)
            equippeditems = {}
            slotlist = set()

            normalitems = itemtools.filter_by_quality(database.load_schema_cached(web.ctx.language), "0")
            for item in normalitems:
                classes = item.get_equipable_classes()
                for c in classes:
                    if c not in equippeditems:
                        equippeditems[c] = {}

                    slot = item.get_slot().title()
                    slotlist.add(slot)
                    if slot not in equippeditems[c]:
                        equippeditems[c][slot] = []

                    equippeditems[c][slot].append(itemtools.process_attributes([item])[0])

            for item in items:
                classes = item.get_equipped_classes()
                for c in classes:
                    slot = item.get_slot().title()
                    slotlist.add(slot)
                    if slot not in equippeditems[c] or equippeditems[c][slot][0].get_quality()["id"] == 0:
                        equippeditems[c][slot] = []
                    equippeditems[c][slot].append(itemtools.process_attributes([item])[0])

            return templates.loadout(userp, equippeditems,
                                     steam.tf2.item.equipped_classes.values(), sorted(slotlist))
        except steam.tf2.TF2Error as E:
            return templates.error("Backpack error: {0}".format(E))
        except steam.user.ProfileError as E:
            return templates.error("Profile error: {0}".format(E))
        except KeyboardInterrupt:
            return templates.error("Couldn't load loadout page")

class attrib_dump:
    """ Dumps all schema attributes in a pretty way """

    def GET(self):
        try:
            query = web.input()
            schema = database.load_schema_cached(web.ctx.language)
            attribs = schema.get_attributes()

            attachment_check = query.get("att")
            if attachment_check:
                items = schema
                attached_items = []

                for item in items:
                    attrs = item.get_attributes()
                    for attr in attrs:
                        attr_name = attr.get_name()
                        if attachment_check == attr_name:
                            attached_items.append(item)
                            break

                return templates.schema_dump(itemtools.process_attributes(attached_items), [], attrdump = attachment_check)

            if query.get("wikitext"):
                web.header("Content-Type", "text/plain; charset=UTF-8")
                return web.template.render(config.template_dir,
                                           globals = render_globals).attrib_wiki_dump(attribs)

            return templates.attrib_dump(attribs)
        except:
            return templates.error("Couldn't load attributes")

class user_completion:
    """ Searches for an account matching the username given in the query
    and returns a JSON object
    Yes it's dirty, yes it'll probably die if Valve changes the layout.
    Yes it's Valve's fault for not providing an equivalent API call.
    Yes I can't use minidom because I would have to replace unicode chars
    because of Valve's lazy encoding.
    Yes I'm designing it to be reusable by other people and myself. """

    _community_url = "http://steamcommunity.com/"
    def GET(self, user):
        search_url = self._community_url + "actions/Search?T=Account&K={0}".format(web.urlquote(user))

        try:
            res = urllib2.urlopen(search_url).read().split('<a class="linkTitle" href="')
            userlist = []

            for user in res:
                if user.startswith(self._community_url):
                    userobj = {
                        "persona": user[user.find(">") + 1:user.find("<")],
                        "id": os.path.basename(user[:user.find('"')])
                        }
                    if user.startswith(self._community_url + "profiles"):
                        userobj["id_type"] = "id64"
                    else:
                        userobj["id_type"] = "id"
                    userlist.append(userobj)
            return json.dumps(userlist)
        except:
            return "{}"

class pack_item:
    def GET(self, iid):
        schema = database.load_schema_cached(web.ctx.language)

        def item_get(id64):
            item = database.fetch_item_for_id(id64)
            if not item:
                item = schema[long(id64)]
            return item

        try:
            user = None
            item_outdated = False
            idl = iid.split('/')
            if len(idl) == 1:
                idl.append(idl[0])
            theitem = item_get(idl[1])
            if not isinstance(theitem, steam.tf2.item):
                user = database.load_profile_cached(str(theitem["owner"]), stale = True)
                theitem = steam.tf2.item(schema, theitem)
                if user:
                    backpack = database.fetch_pack_for_user(user)
                    if backpack and theitem.get_id() not in pickle.loads(str(backpack["backpack"])):
                        item_outdated = True

            item = itemtools.process_attributes([theitem])[0]
            if web.input().get("contents"):
                itemcontents = item.optf2.get("gift_item")
                if itemcontents: item = itemtools.process_attributes([itemcontents])[0]
        except urllib2.URLError:
            return templates.error("Couldn't connect to Steam")
        except:
            return templates.item_error_notfound(idl[1])
        return templates.item(user, item, item_outdated)

class persona:
    def GET(self, id):
        theobject = {"persona": "", "realname": ""}
        callback = web.input().get("jsonp")

        try:
            user = steam.user.profile(id)
            persona = user.get_persona()
            realname = user.get_real_name()
            theobject["persona"] = persona
            theobject["realname"] = realname
            theobject["id64"] = str(user.get_id64())
            theobject["avatarurl"] = user.get_avatar_url(user.AVATAR_SMALL)
        except: pass

        web.header("Content-Type", "text/javascript")
        if not callback:
            return json.dumps(theobject)
        else:
            return callback + '(' + json.dumps(theobject) + ');'

class about:
    def GET(self):
        return templates.about()

class pack_fetch:
    def _get_page_for_sid(self, sid):
        if not sid:
            return templates.error("Need an ID")
        try:
            user = database.load_profile_cached(sid)
        except urllib2.URLError:
            return templates.error("Couldn't connect to Steam")
        except steam.user.ProfileError as E:
            search = json.loads(user_completion().GET(sid))
            nuser = None
            for result in search:
                if result["persona"] == sid:
                    nuser = result["id"]
                    break
            for result in search:
                if result["persona"].lower() == sid.lower():
                    nuser = result["id"]
                    break
            for result in search:
                if result["persona"].lower().find(sid.lower()) != -1:
                    nuser = result["id"]
                    break
            if nuser:
                try:
                    user = database.load_profile_cached(nuser)
                except:
                    return templates.error("Failed to load user profile")
            else:
                return templates.error("Bad profile name ({0})".format(E))

        query = web.input()
        sortby = query.get("sort", "cell")
        sortclass = query.get("sortclass")
        packtime = query.get("time")
        filter_quality = query.get("quality")

        try:
            items = database.load_pack_cached(user, date = packtime)
            if not items and user.get_visibility() != "public":
                raise steam.user.ProfileError("Backpack is private")

            timestamps = []
            for ts in database.fetch_pack_for_user(user, tl_size = 10):
                prettyts = time.ctime(ts["timestamp"])
                timestamps.append([ts["timestamp"], prettyts])

            filter_classes = itemtools.get_equippable_classes(items)
            filter_qualities = itemtools.get_present_qualities(items)
            if sortclass:
                items = itemtools.filter_by_class(items, sortclass)
            if filter_quality:
                items = itemtools.filter_by_quality(items, filter_quality)

            itemtools.process_attributes(items)
            stats = itemtools.get_stats(items)

            baditems = itemtools.get_invalid_pos(items)

            items = itemtools.sort(items, sortby)

            total_pages = len(items) / 50
            if len(items) % 50 != 0:
                total_pages += 1
            total_pages = range(1, total_pages + 1)

            for bitem in baditems:
                if bitem in items:
                    bpos = bitem.get_position()
                    if bpos > 0 and sortby == "cell":
                        items[items.index(bitem)] = None
                    else:
                        items.remove(bitem)
                        items.append(None)

        except steam.tf2.TF2Error as E:
            return templates.error("Failed to load backpack ({0})".format(E))
        except steam.user.ProfileError as E:
            return templates.error("Failed to load profile ({0})".format(E))
        except:
            return templates.error("Failed to load backpack")

        isvalve = (user.get_primary_group() == valve_group_id)
        views = 0
        uid64 = user.get_id64()
        ipaddr = web.ctx.ip

        with db_obj.transaction():
            count = db_obj.select("search_count", where = "id64 = $id64 AND ip = $ip",
                                  vars = {"ip": ipaddr, "id64": uid64})
            if len(count) <= 0:
                db_obj.insert("search_count", ip = ipaddr, id64 = uid64)
                views = 1
            db_obj.query("INSERT INTO unique_views (id64, persona, valve) VALUES " +
                         "($id64, $p, $v) ON DUPLICATE KEY UPDATE id64=VALUES(id64), persona=VALUES(persona),"
                         " valve=VALUES(valve), count=count+$c", vars = {"id64": uid64,
                                                                         "p": user.get_persona(),
                                                                         "v": isvalve,
                                                                         "c": views})
            views = db_obj.select("unique_views", what = "count", where = "id64 = $id64",
                                  vars = {"id64": uid64})[0]["count"]

        web.ctx.env["optf2_rss_url"] = "{0}feed/{1}".format(config.virtual_root, uid64)
        web.ctx.env["optf2_rss_title"] = "{0}'s Backpack".format(user.get_persona().encode("utf-8"))

        return templates.inventory(user, isvalve, items, views,
                                   filter_classes, baditems,
                                   stats, timestamps, filter_qualities,
                                   total_pages)

    def GET(self, sid):
        return self._get_page_for_sid(sid)

class pack_feed:
    def GET(self, sid):
        try:
            user = database.load_profile_cached(sid, stale = True)
            items = database.load_pack_cached(user)
            itemtools.process_attributes(items)
        except Exception as E:
            return templates.error(str(E))
        web.header("Content-Type", "application/rss+xml")
        return web.template.render(config.template_dir,
                                   globals = render_globals).inventory_feed(user, items)

class index:
    def GET(self):
        user = web.input().get("user")

        if user:
            if user.endswith('/'): user = user[:-1]
            raise web.seeother(config.virtual_root + "user/" + os.path.basename(user))

        countlist = db_obj.select("unique_views", order = "count DESC", limit = config.top_backpack_rows)
        return templates.index(countlist)

class openid_consume:
    def GET(self):
        openid_store = sqlstore.MySQLStore(db_obj._db_cursor().connection)

        openid = consumer.Consumer(session, openid_store)
        openid_realm = web.ctx.homedomain
        openid_return_url = openid_realm + config.virtual_root + "openid"
        try:
            auth = openid.begin("http://steamcommunity.com/openid/")
            openid_auth_url = auth.redirectURL(openid_realm, return_to = openid_return_url)
        except: return templates.error("Can't connect to Steam")

        if web.input().get("openid.return_to"):
            openid_return_url = openid_realm + config.virtual_root + "openid"
            response = openid.complete(web.input(), openid_return_url)
            if response.status != consumer.SUCCESS or not response.identity_url:
                return templates.error("Login Error")
            session["identity_hash"] = make_openid_hash(response.identity_url) + "," + response.identity_url

            raise web.seeother(config.virtual_root + "user/" + os.path.basename(response.identity_url))
        else:
            raise web.seeother(openid_auth_url)

if config.enable_fastcgi:
    web.wsgi.runwsgi = lambda func, addr=None: web.wsgi.runfcgi(func, addr)

if __name__ == "__main__":
    app.run()
