import web
import template
import steam
from optf2.backend import database
from optf2.backend import items as itemtools
from optf2.backend import config
from optf2.backend import log
from optf2.frontend import markup

templates = template.template

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
                loadout.setdefault(cid, {})
                classmap.add((cid, name))
                # WORKAROUND: There is one unique shotgun for all classes in TF2,
                # and it's in the primary slot. This has obvious problems
                if item["sid"] == 199 and name != "Engineer":
                    slot = "Secondary"
                else:
                    slot = item.get("slot") or str(slots.get(cid, ''))
                    slot = slot.title()
                if slot not in sortedslots and slot not in slotlist: slotlist.append(slot)
                if slot not in loadout[cid] or (quality != 0 and loadout[cid][slot][0]["quality"] == "normal"):
                    loadout[cid][slot] = []
                loadout[cid][slot].append(item)

        return loadout, slotlist, classmap

    def GET(self, app, user):
        markup.init_theme(app)
        markup.set_navlink()
        try:
            cache = database.cache(mode = app)

            userp = cache.get_profile(user)
            items = cache.get_backpack(userp)["items"].values()
            equippeditems = {}
            classmap = set()
            slotlist = []
            self._app = app

            # initial normal items
            try:
                schema = cache.get_schema()
                normalitems = itemtools.filter_by_quality([cache._build_processed_item(item) for item in schema], "normal")
                equippeditems, slotlist, classmap = self.build_loadout(normalitems, equippeditems, slotlist, classmap)
            except database.CacheEmptyError:
                pass

            # Real equipped items
            equippeditems, slotlist, classmap = self.build_loadout(items, equippeditems, slotlist, classmap)

            return templates.loadout(app, userp, equippeditems, sorted(classmap), self._slots_sorted + sorted(slotlist))
        except steam.items.Error as E:
            return templates.error("Backpack error: {0}".format(E))
        except steam.user.ProfileError as E:
            return templates.error("Profile error: {0}".format(E))
        except steam.base.HttpError as E:
            return templates.error("Couldn't connect to Steam (HTTP {0})".format(E))

    def __init__(self):
        # Slots that should be arranged in this order
        self._slots_sorted = ["Head", "Misc", "Primary", "Secondary", "Melee", "Pda", "Pda2", "Building", "Action"]

class item:
    def GET(self, app, iid):
        cache = database.cache(mode = app)
        user = None

        markup.init_theme(app)

        try:
            schema = cache.get_schema()
            item = cache._build_processed_item(schema[long(iid)])

            if web.input().get("contents"):
                contents = item.get("contents")
                if contents:
                    item = contents
        except steam.base.HttpError as E:
            return templates.error("Couldn't connect to Steam (HTTP {0})".format(E))
        except steam.items.Error as E:
            return templates.error("Couldn't open schema: {0}".format(E))
        except KeyError:
            return templates.item_error_notfound(iid)
        except database.CacheEmptyError as E:
            return templates.error(E)

        caps = markup.get_capability_strings(itemtools.get_present_capabilities([item]))

        try:
            assets = cache.get_assets()
            price = markup.generate_item_price_string(item, assets)
        except database.CacheEmptyError:
            price = None

        return templates.item(app, user, item, price = price, caps = caps)

class live_item:
    """ More or less temporary until database stuff is sorted """
    def GET(self, app, user, iid):
        cache = database.cache(mode = app)
        markup.init_theme(app)
        try:
            user = cache.get_profile(user)
            items = cache.get_backpack(user)
            item = items["items"][long(iid)]

            if web.input().get("contents"):
                contents = item.get("contents")
                if contents:
                    item = contents
        except steam.base.HttpError as E:
            return templates.error("Couldn't connect to Steam (HTTP {0})".format(E))
        except steam.user.ProfileError as E:
            return templates.error("Can't retrieve user profile data: {0}".format(E))
        except steam.items.Error as E:
            return templates.error("Couldn't open backpack: {0}".format(E))
        except KeyError:
            return templates.item_error_notfound(iid)
        return templates.item(app, user, item)

class fetch:
    def _get_inv(self, user, cache):
        pack = cache.get_backpack(user)
        cell_count = pack["cells"]
        items = pack["items"].values()

        return items, cell_count

    def _get_profile(self, sid, cache):
        return cache.get_profile(sid)

    def GET(self, app, sid):
        sid = sid.strip('/').split('/')
        if len(sid) > 0: sid = sid[-1]

        if not sid:
            return templates.error("Need an ID")

        query = web.input()
        sortby = query.get("sort", "cell")
        filter_class = query.get("cls")
        filter_quality = query.get("quality")

        # TODO: Possible custom page sizes via query part
        dims = markup.get_page_sizes().get(app)
        try: pagesize = int(dims["width"] * dims["height"])
        except TypeError: pagesize = None

        markup.init_theme(app)
        markup.set_navlink()

        try:
            cache = database.cache(mode = app)
            user = self._get_profile(sid, cache)
            items, cell_count = self._get_inv(user, cache)

            filter_classes = markup.sorted_class_list(itemtools.get_equippable_classes(items, cache))
            filter_qualities = markup.get_quality_strings(itemtools.get_present_qualities(items), cache)
            if len(filter_classes) <= 1: filter_classes = None
            if len(filter_qualities) <= 1: filter_qualities = None

            if filter_class:
                items = itemtools.filter_by_class(items, markup.get_class_for_id(filter_class, app)[0])
            if filter_quality:
                items = itemtools.filter_by_quality(items, filter_quality)

            stats = itemtools.get_stats(items)

            sorted_items = itemtools.sort(items, sortby)
            baditems = []
            (items, baditems) = itemtools.build_page_object(sorted_items, pagesize = pagesize, ignore_position = (sortby != "cell"))

            price_stats = itemtools.get_price_stats(sorted_items, cache)

        except steam.items.Error as E:
            return templates.error("Failed to load backpack ({0})".format(E))
        except steam.user.ProfileError as E:
            return templates.error("Failed to load profile ({0})".format(E))
        except steam.base.HttpError as E:
            return templates.error("Couldn't connect to Steam (HTTP {0})".format(E))
        except database.CacheEmptyError as E:
            return templates.error(E)

        web.ctx.rss_feeds = [("{0}'s Backpack".format(user["persona"].encode("utf-8")),
                              markup.generate_root_url("feed/" + str(user["id64"]), app))]

        return templates.inventory(app, user, items, baditems,
                                   filter_classes, filter_qualities, stats,
                                   price_stats, cell_count)

class feed:
    def GET(self, app, sid):
        renderer = web.template.render(config.ini.get("resources", "template-dir"),
                                       globals = template.globals)

        web.header("Content-Type", "application/rss+xml")

        try:
            cache = database.cache(mode = app)
            user = cache.get_profile(sid)
            items = cache.get_backpack(user)["items"].values()
            items = itemtools.sort(items, web.input().get("sort", "time"))

            return renderer.inventory_feed(app, user, items[:config.ini.getint("rss", "inventory-max-items")])

        except (steam.user.ProfileError, steam.items.Error, steam.base.HttpError) as E:
            return renderer.inventory_feed(app, None, [], erritem = E)

        except Exception as E:
            log.main.error(str(E))
            return renderer.inventory_feed(app, None, [], erritem = E)
