import web
import template
import steam
from optf2.backend import database
from optf2.backend import items as itemtools
from optf2.backend import config
from optf2.backend import log
from optf2.frontend import markup

templates = template.template
error_page = templates.errors

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
        app = database.app_aliases.get(app, app)
        self._cid = cid
        markup.init_theme(app)
        try:
            userp = database.user(user).load()
            pack = database.inventory(userp, scope = app).load()
            items = pack["items"].values()
            equippeditems = {}
            classmap = set()
            slotlist = []
            self._app = app

            markup.set_navlink(markup.generate_root_url("loadout/{0}".format(userp["id64"]), app))

            # initial normal items
            try:
                sitems = database.schema(scope = app).processed_items.values()
                normalitems = itemtools.filtering(sitems).byQuality("normal")
                equippeditems, slotlist, classmap = self.build_loadout(normalitems, equippeditems, slotlist, classmap)
            except database.CacheEmptyError:
                pass

            # Real equipped items
            equippeditems, slotlist, classmap = self.build_loadout(items, equippeditems, slotlist, classmap)

            return templates.loadout(app, userp, equippeditems, sorted(classmap), self._slots_sorted + sorted(slotlist), cid)
        except steam.items.InventoryError as E:
            raise web.NotFound(error_page.generic("Backpack error: {0}".format(E)))
        except steam.user.ProfileError as E:
            raise web.NotFound(error_page.generic("Profile error: {0}".format(E)))
        except steam.api.HTTPError as E:
            raise web.NotFound(error_page.generic("Couldn't connect to Steam (HTTP {0})".format(E)))
        except itemtools.ItemBackendUnimplemented:
            raise web.NotFound(error_page.generic("No backend found to handle loadouts for these items"))

    def __init__(self):
        self._cid = None
        # Slots that should be arranged in this order
        self._slots_sorted = ["Head", "Misc", "Primary", "Secondary", "Melee", "Pda", "Pda2", "Building", "Action"]

class item:
    def GET(self, app, iid):
        user = None

        markup.init_theme(app)

        try:
            sitems = database.schema(scope = app).processed_items
            item = sitems[iid]

            if web.input().get("contents"):
                contents = item.get("contents")
                if contents:
                    item = contents
        except steam.api.HTTPError as E:
            raise web.NotFound(error_page.generic("Couldn't connect to Steam (HTTP {0})".format(E)))
        except steam.items.SchemaError as E:
            raise web.NotFound(error_page.generic("Couldn't open schema: {0}".format(E)))
        except KeyError:
            raise web.NotFound(templates.item_error_notfound(iid))
        except database.CacheEmptyError as E:
            raise web.NotFound(error_page.generic(E))
        except itemtools.ItemBackendUnimplemented:
            raise web.NotFound(error_page.generic("No backend found to handle the given item, this could mean that the item has no available associated schema (yet)"))

        caps = markup.get_capability_strings(itemtools.get_present_capabilities([item]))

        try:
            assets = database.assets(scope = app).price_map
            price = markup.generate_item_price_string(item, assets)
        except database.CacheEmptyError:
            price = None

        # Strip off quality prefix for possessive name
        itemname = item["mainname"]
        if itemname.startswith("The "):
            item["ownedname"] = itemname[4:]
        else:
            item["ownedname"] = itemname

        return templates.item(app, user, item, price = price, caps = caps)

class live_item:
    """ More or less temporary until database stuff is sorted """
    def GET(self, app, user, iid):
        markup.init_theme(app)

        try:
            user, items = database.load_inventory(user, scope = app)
        except steam.api.HTTPError as E:
            raise web.NotFound(error_page.generic("Couldn't connect to Steam (HTTP {0})".format(E)))
        except steam.user.ProfileError as E:
            raise web.NotFound(error_page.generic("Can't retrieve user profile data: {0}".format(E)))
        except steam.items.InventoryError as E:
            raise web.NotFound(error_page.generic("Couldn't open backpack: {0}".format(E)))

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
                raise web.NotFound(templates.item_error_notfound(iid))

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

        return templates.item(app, user, item)

class fetch:
    def GET(self, app, sid):
        app = database.app_aliases.get(app, app)
        sid = sid.strip('/').split('/')
        if len(sid) > 0: sid = sid[-1]

        if not sid:
            raise web.NotFound(error_page.generic("Need an ID"))

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
            user, pack = database.load_inventory(sid, app)
            schema = None

            try:
                schema = database.schema(scope = app)
            except itemtools.ItemBackendUnimplemented:
                pass

            cell_count = pack["cells"]
            items = pack["items"].values()

            filters = itemtools.filtering(items)
            filter_classes = markup.sorted_class_list(itemtools.get_equippable_classes(items), app)
            filter_qualities = markup.get_quality_strings(itemtools.get_present_qualities(items), schema)
            if len(filter_classes) <= 1: filter_classes = None
            if len(filter_qualities) <= 1: filter_qualities = None

            if filter_class:
                items = filters.byClass(markup.get_class_for_id(filter_class, app)[0])
            if filter_quality:
                items = filters.byQuality(filter_quality)

            stats = itemtools.get_stats(items)

            sorter = itemtools.sorting(items)
            sorted_items = sorter.sort(sortby)

            baditems = []
            (items, baditems) = itemtools.build_page_object(sorted_items, pagesize = pagesize, ignore_position = sortby)

            price_stats = itemtools.get_price_stats(sorted_items, database.assets(scope = app))

        except steam.items.InventoryError as E:
            raise web.NotFound(error_page.generic("Failed to load backpack ({0})".format(E)))
        except steam.user.ProfileError as E:
            raise web.NotFound(error_page.generic("Failed to load profile ({0})".format(E)))
        except steam.api.HTTPError as E:
            raise web.NotFound(error_page.generic("Couldn't connect to Steam (HTTP {0})".format(E)))
        except database.CacheEmptyError as E:
            raise web.NotFound(error_page.generic(E))

        web.ctx.rss_feeds = [("{0}'s Backpack".format(user["persona"].encode("utf-8")),
                              markup.generate_root_url("feed/" + str(user["id64"]), app))]

        return templates.inventory(app, user, items, sorter.get_sort_methods(), baditems,
                                   filter_classes, filter_qualities, stats,
                                   price_stats, cell_count)

class feed:
    def GET(self, app, sid):
        renderer = web.template.render(config.ini.get("resources", "template-dir"),
                                       globals = template.globals)

        try:
            user, pack = database.load_inventory(sid, scope = app)
            items = pack["items"].values()
            sorter = itemtools.sorting(items)
            items = sorter.sort(web.input().get("sort", sorter.byTime))
            cap = config.ini.getint("rss", "inventory-max-items")

            if cap: items = items[:cap]

            web.header("Content-Type", "application/rss+xml")
            return renderer.inventory_feed(app, user, items)

        except (steam.user.ProfileError, steam.items.InventoryError, steam.api.HTTPError) as E:
            raise rssNotFound()
        except Exception as E:
            log.main.error(str(E))
            raise rssNotFound()
