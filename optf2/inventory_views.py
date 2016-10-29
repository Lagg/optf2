import web
import steam
from optf2 import models
from optf2 import config
from optf2 import log
from optf2 import markup
from optf2 import views
from optf2.views import template, template_setup

_feed_renderer = template_setup(config.ini.get("resources", "template-dir"))

class rssNotFound(web.HTTPError):
    def __init__(self, message = None):
        status = "404 Not Found"
        headers = {"Content-Type": "application/rss+xml"}
        web.HTTPError.__init__(self, status, headers, message)

class loadout:
    """ User loadout lists """

    def build_loadout(self, items, loadout, slotlist, classmap):
        sortedslots = self._slots_sorted

        for item in items:
            quality = item.get("quality", "normal")
            equipped = item.get("equipped", {})
            slots = equipped

            if quality == "normal":
                classes = item.get("equipable", [])
            else:
                classes = equipped.keys()

            for c in classes:
                cid, name = markup.get_class_for_id(c, self._app)
                if self._cid and str(cid) != str(self._cid): continue
                loadout.setdefault(cid, {})
                classmap.add((cid, name))
                # WORKAROUND: There is one unique shotgun for all classes in TF2,
                # and it's in the primary slot. This has obvious problems
                if item["sid"] == 199 and name != "Engineer":
                    slot = "Secondary"
                else:
                    slot = str(item.get("slot") or slots.get(str(cid), ''))
                    slot = slot.title()
                if slot not in sortedslots and slot not in slotlist: slotlist.append(slot)
                if slot not in loadout[cid] or (quality != 0 and loadout[cid][slot][0]["quality"] == "normal"):
                    loadout[cid][slot] = []
                loadout[cid][slot].append(item)

        return loadout, slotlist, classmap

    def GET(self, app, user, cid = None):
        app = models.app_aliases.get(app, app)
        self._cid = cid
        markup.init_theme(app)
        try:
            userp = models.user(user).load()
            pack = models.inventory(userp, scope = app).load()
            items = pack["items"].values()
            equippeditems = {}
            classmap = set()
            slotlist = []
            self._app = app

            markup.set_navlink(markup.generate_root_url("loadout/{0}".format(userp["id64"]), app))

            # initial normal items
            try:
                sitems = models.schema(scope = app).processed_items.values()
                normalitems = views.filtering(sitems).byQuality("normal")
                equippeditems, slotlist, classmap = self.build_loadout(normalitems, equippeditems, slotlist, classmap)
            except models.CacheEmptyError:
                pass

            # Real equipped items
            equippeditems, slotlist, classmap = self.build_loadout(items, equippeditems, slotlist, classmap)

            return template.loadout(app, userp, equippeditems, sorted(classmap), self._slots_sorted + sorted(slotlist), cid)
        except steam.items.InventoryError as E:
            raise web.NotFound(template.errors.generic("Backpack error: {0}".format(E)))
        except steam.user.ProfileError as E:
            raise web.NotFound(template.errors.generic("Profile error: {0}".format(E)))
        except steam.api.HTTPError as E:
            raise web.NotFound(template.errors.generic("Couldn't connect to Steam (HTTP {0})".format(E)))
        except models.ItemBackendUnimplemented:
            raise web.NotFound(template.errors.generic("No backend found to handle loadouts for these items"))

    def __init__(self):
        self._cid = None
        # Slots that should be arranged in this order
        self._slots_sorted = ["Head", "Misc", "Primary", "Secondary", "Melee", "Pda", "Pda2", "Building", "Action"]

class item:
    def GET(self, app, iid):
        user = None

        markup.init_theme(app)

        try:
            sitems = models.schema(scope = app).processed_items
            item = sitems[iid]

            if web.input().get("contents"):
                contents = item.get("contents")
                if contents:
                    item = contents
        except steam.api.HTTPError as E:
            raise web.NotFound(template.errors.generic("Couldn't connect to Steam (HTTP {0})".format(E)))
        except steam.items.SchemaError as E:
            raise web.NotFound(template.errors.generic("Couldn't open schema: {0}".format(E)))
        except KeyError:
            raise web.NotFound(template.item_error_notfound(iid))
        except models.CacheEmptyError as E:
            raise web.NotFound(template.errors.generic(E))
        except models.ItemBackendUnimplemented:
            raise web.NotFound(template.errors.generic("No backend found to handle the given item, this could mean that the item has no available associated schema (yet)"))

        caps = markup.get_capability_strings(item.get("caps", []))

        try:
            assets = models.assets(scope = app).price_map
            price = markup.generate_item_price_string(item, assets)
        except models.CacheEmptyError:
            price = None

        # Strip off quality prefix for possessive name
        itemname = item["mainname"]
        if itemname.startswith("The "):
            item["ownedname"] = itemname[4:]
        else:
            item["ownedname"] = itemname

        return template.item(app, user, item, price = price, caps = caps)

class live_item:
    """ More or less temporary until database stuff is sorted """
    def GET(self, app, user, iid):
        markup.init_theme(app)

        try:
            user, items = models.load_inventory(user, scope = app)
        except steam.api.HTTPError as E:
            raise web.NotFound(template.errors.generic("Couldn't connect to Steam (HTTP {0})".format(E)))
        except steam.user.ProfileError as E:
            raise web.NotFound(template.errors.generic("Can't retrieve user profile data: {0}".format(E)))
        except steam.items.InventoryError as E:
            raise web.NotFound(template.errors.generic("Couldn't open backpack: {0}".format(E)))

        item = None
        try:
            item = items["items"][iid]
        except KeyError:
            for cid, bpitem in items["items"].iteritems():
                oid = bpitem.get("oid")
                if oid == long(iid):
                    item = bpitem
                    break
            if not item:
                raise web.NotFound(template.item_error_notfound(iid))

        if web.input().get("contents"):
            contents = item.get("contents")
            if contents:
                item = contents

        # Strip off quality prefix for possessive name
        itemname = item["mainname"]
        if itemname.startswith("The "):
            item["ownedname"] = itemname[4:]
        else:
            item["ownedname"] = itemname

        return template.item(app, user, item)

class fetch:
    def GET(self, app, sid):
        app = models.app_aliases.get(app, app)
        sid = sid.strip('/').split('/')
        if len(sid) > 0: sid = sid[-1]

        if not sid:
            raise web.NotFound(template.errors.generic("Need an ID"))

        query = web.input()
        sortby = query.get("sort")
        filter_class = query.get("cls")
        filter_quality = query.get("quality")

        # TODO: Possible custom page sizes via query part
        dims = markup.get_page_sizes().get(app)
        try: pagesize = int(dims["width"] * dims["height"])
        except TypeError: pagesize = None

        markup.init_theme(app)
        markup.set_navlink()

        try:
            user, pack = models.load_inventory(sid, app)
            schema = None

            try:
                schema = models.schema(scope = app)
            except models.ItemBackendUnimplemented:
                pass

            cell_count = pack["cells"]
            items = pack["items"].values()

            filters = views.filtering(items)
            dropdowns = views.build_dropdowns(items)
            filter_classes = markup.sorted_class_list(dropdowns["equipable_classes"], app)
            filter_qualities = markup.get_quality_strings(dropdowns["qualities"], schema)
            if len(filter_classes) <= 1: filter_classes = None
            if len(filter_qualities) <= 1: filter_qualities = None

            if filter_class:
                items = filters.byClass(markup.get_class_for_id(filter_class, app)[0])

            if filter_quality:
                items = filters.byQuality(filter_quality)

            sorter = views.sorting(items)
            sorted_items = sorter.sort(sortby)

            item_page = views.item_page(items)
            stats = item_page.summary

            baditems = []
            items, baditems = item_page.build_page(pagesize=pagesize, ignore_pos=sortby)

            price_stats = item_page.build_price_summary(models.assets(scope = app))

        except steam.items.InventoryError as E:
            raise web.NotFound(template.errors.generic("Failed to load backpack ({0})".format(E)))
        except steam.user.ProfileError as E:
            raise web.NotFound(template.errors.generic("Failed to load profile ({0})".format(E)))
        except steam.api.HTTPError as E:
            raise web.NotFound(template.errors.generic("Couldn't connect to Steam (HTTP {0})".format(E)))
        except models.CacheEmptyError as E:
            raise web.NotFound(template.errors.generic(E))
        except:
            raise web.NotFound(template.errors.generic("Couldn't load feed"))

        web.ctx.rss_feeds = [("{0}'s Backpack".format(user["persona"].encode("utf-8")),
                              markup.generate_root_url("feed/" + str(user["id64"]), app))]

        return template.inventory(app, user, items, sorter.get_sort_methods(), baditems,
                                   filter_classes, filter_qualities, stats,
                                   price_stats, cell_count)

class feed:
    def GET(self, app, sid):
        try:
            user, pack = models.load_inventory(sid, scope = app)
            items = pack["items"].values()
            sorter = views.sorting(items)
            items = sorter.sort(web.input().get("sort", sorter.byTime))
            cap = config.ini.getint("rss", "inventory-max-items")

            if cap: items = items[:cap]

            web.header("Content-Type", "application/rss+xml")
            return _feed_renderer.inventory_feed(app, user, items)

        except (steam.user.ProfileError, steam.items.InventoryError, steam.api.HTTPError) as E:
            raise rssNotFound()
        except Exception as E:
            log.main.error(str(E))
            raise rssNotFound()

class sim_selector:
    def GET(self, user):
        baseurl = user.strip('/').split('/')
        if len(baseurl) > 0:
            user = baseurl[-1]

        if not user:
            raise steam.items.InventoryError("Need an ID")

        try:
            prof = models.user(user).load()
            ctx = models.sim_context(prof).load()
            for ct in (ctx or []):
                ct.setdefault("inventory_logo", '/static/pixel.png')

            return template.sim_selector(prof, ctx)
        except steam.items.InventoryError as E:
            raise web.NotFound(template.errors.generic("Failed to load backpack ({0})".format(E)))
        except steam.user.ProfileError as E:
            raise web.NotFound(template.errors.generic("Failed to load profile ({0})".format(E)))
        except steam.api.HTTPError as E:
            raise web.NotFound(template.errors.generic("Couldn't connect to Steam (HTTP {0})".format(E)))
        except models.CacheEmptyError as E:
            raise web.NotFound(template.errors.generic(E))
