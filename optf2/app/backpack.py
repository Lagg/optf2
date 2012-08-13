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
                cid, name = markup.get_class_for_id(c)
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

    def GET(self, user):
        try:
            cache = database.cache()

            userp = cache.get_profile(user)
            schema = cache.get_schema()
            items = cache.get_backpack(userp)["items"].values()
            equippeditems = {}
            classmap = set()
            slotlist = []

            # initial normal items
            normalitems = itemtools.filter_by_quality([cache._build_processed_item(item) for item in schema], "normal")
            equippeditems, slotlist, classmap = self.build_loadout(normalitems, equippeditems, slotlist, classmap)

            # Real equipped items
            equippeditems, slotlist, classmap = self.build_loadout(items, equippeditems, slotlist, classmap)

            return templates.loadout(userp, equippeditems, sorted(classmap), self._slots_sorted + sorted(slotlist))
        except steam.items.Error as E:
            return templates.error("Backpack error: {0}".format(E))
        except steam.user.ProfileError as E:
            return templates.error("Profile error: {0}".format(E))
        except steam.base.HttpError:
            return templates.error("Couldn't connect to Steam")

    def __init__(self):
        # Slots that should be arranged in this order
        self._slots_sorted = ["Head", "Misc", "Primary", "Secondary", "Melee", "Pda", "Pda2", "Building", "Action"]

class item:
    def GET(self, iid):
        cache = database.cache()
        schema = cache.get_schema()
        assets = cache.get_assets()
        user = None
        item_outdated = False
        try:
            item = cache._build_processed_item(schema[long(iid)])

            if web.input().get("contents"):
                contents = item.get("contents")
                if contents:
                    item = contents
        except steam.base.HttpError:
            return templates.error("Couldn't connect to Steam")
        except steam.items.Error as E:
            return templates.error("Couldn't open schema: {0}".format(E))
        except KeyError:
            return templates.item_error_notfound(iid)

        caps = markup.get_capability_strings(itemtools.get_present_capabilities([item]))
        price = markup.generate_item_price_string(item, assets)

        return templates.item(user, item, item_outdated, price = price, caps = caps)

class live_item:
    """ More or less temporary until database stuff is sorted """
    def GET(self, user, iid):
        item_outdated = False
        cache = database.cache()
        try:
            user = cache.get_profile(user)
            items = cache.get_backpack(user)

            item = items["items"][long(iid)]

            if web.input().get("contents"):
                contents = item.get("contents")
                if contents:
                    item = contents
        except steam.base.HttpError:
            return templates.error("Couldn't connect to Steam")
        except steam.user.ProfileError as E:
            return templates.error("Can't retrieve user profile data: {0}".format(E))
        except steam.items.Error as E:
            return templates.error("Couldn't open backpack: {0}".format(E))
        except KeyError:
            return templates.item_error_notfound(iid)
        return templates.item(user, item, item_outdated)

class fetch:
    def GET(self, sid):
        sid = sid.strip('/').split('/')
        if len(sid) > 0: sid = sid[-1]

        if not sid:
            return templates.error("Need an ID")

        query = web.input()
        sortby = query.get("sort", "cell")
        sortclass = query.get("sortclass")
        filter_quality = query.get("quality")
        cache = database.cache()
        schema = cache.get_schema()

        try:
            user = cache.get_profile(sid)
            pack = cache.get_backpack(user)
            cell_count = pack["cells"]
            items = pack["items"].values()

            filter_classes = markup.sorted_class_list(itemtools.get_equippable_classes(items, cache))
            filter_qualities = markup.get_quality_strings(itemtools.get_present_qualities(items), cache)
            if sortclass:
                items = itemtools.filter_by_class(items, sortclass)
            if filter_quality:
                items = itemtools.filter_by_quality(items, filter_quality)

            stats = itemtools.get_stats(items)

            sorted_items = itemtools.sort(items, sortby)
            baditems = []
            (items, baditems) = itemtools.build_page_object(sorted_items, ignore_position = (sortby != "cell"))

            price_stats = itemtools.get_price_stats(sorted_items, cache)

        except steam.items.Error as E:
            return templates.error("Failed to load backpack ({0})".format(E))
        except steam.user.ProfileError as E:
            return templates.error("Failed to load profile ({0})".format(E))
        except steam.base.HttpError as E:
            return templates.error("Couldn't connect to Steam (HTTP {0})".format(E))

        views = 0

        web.ctx.env["optf2_rss_url"] = markup.generate_mode_url("feed/" + str(user["id64"]))
        web.ctx.env["optf2_rss_title"] = "{0}'s Backpack".format(user["persona"].encode("utf-8"))

        return templates.inventory(user, items, views,
                                   filter_classes, baditems,
                                   stats, filter_qualities,
                                   schema._app_id,
                                   price_stats, cell_count)

class feed:
    def GET(self, sid):
        renderer = web.template.render(config.ini.get("resources", "template-dir"),
                                       globals = template.globals)

        web.header("Content-Type", "application/rss+xml")

        try:
            cache = database.cache()
            user = cache.get_profile(sid)
            items = cache.get_backpack(user)["items"].values()
            items = itemtools.sort(items, web.input().get("sort", "time"))

            return renderer.inventory_feed(user, items[:config.ini.getint("rss", "inventory-max-items")])

        except (steam.user.ProfileError, steam.items.Error, steam.base.HttpError) as E:
            return renderer.inventory_feed(None, [], erritem = E)

        except Exception as E:
            log.main.error(str(E))
            return renderer.inventory_feed(None, [], erritem = E)
