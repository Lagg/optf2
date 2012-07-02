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

    def GET(self, user):
        try:
            cache = database.cache()

            userp = cache.get_profile(user)
            schema = cache.get_schema()
            items = itemtools.process_attributes(cache.get_backpack(userp))
            equippeditems = {}
            classmap = {}
            overrides, swappedoverrides = markup.get_class_overrides()
            if overrides: classmap = overrides
            slotlist = ["Head", "Misc", "Primary", "Secondary", "Melee", "Pda", "Pda2", "Building", "Action"]

            normalitems = itemtools.process_attributes(itemtools.filter_by_quality(schema, "0"))
            for item in normalitems:
                classes = item.get_equipable_classes()
                for c in classes:
                    cid, name = markup.get_class_for_id(c)
                    if cid not in equippeditems: equippeditems[cid] = {}
                    if cid not in classmap: classmap[cid] = name

                    slot = item.get_slot() or ""
                    slot = slot.title()
                    if slot not in slotlist: slotlist.append(slot)
                    if slot not in equippeditems[cid]:
                        equippeditems[cid][slot] = []

                    equippeditems[cid][slot].append(item)

            for item in items:
                classes = item.get_equipped_classes()
                for c in classes:
                    cid, name = markup.get_class_for_id(c)
                    if cid not in equippeditems: equippeditems[cid] = {}
                    if cid not in classmap: classmap[cid] = name
                    # WORKAROUND: There is one unique shotgun for all classes, and it's in the primary slot. This
                    # has obvious problems
                    if item.get_schema_id() == 199 and name != "Engineer":
                        slot = "Secondary"
                    else:
                        slot = item.get_slot() or ""
                        slot = slot.title()
                    if slot not in slotlist: slotlist.append(slot)
                    if slot not in equippeditems[cid] or equippeditems[cid][slot][0].get_quality()["id"] == 0:
                        equippeditems[cid][slot] = []
                    equippeditems[cid][slot].append(item)

            return templates.loadout(userp, equippeditems, classmap, slotlist)
        except steam.items.Error as E:
            return templates.error("Backpack error: {0}".format(E))
        except steam.user.ProfileError as E:
            return templates.error("Profile error: {0}".format(E))
        except steam.base.HttpError:
            return templates.error("Couldn't connect to Steam")

class item:
    def GET(self, iid):
        cache = database.cache()
        schema = cache.get_schema()
        assets = cache.get_assets()
        user = None
        item_outdated = False
        try:
            theitem = schema[long(iid)]

            item = itemtools.process_attributes([theitem])[0]
            if web.input().get("contents"):
                itemcontents = item.optf2.get("contents")
                if itemcontents:
                    newitem = itemtools.process_attributes([itemcontents], gift = True)[0]
                    newitem.optf2 = dict(item.optf2, **newitem.optf2)
                    newitem.optf2["container_id"] = item.get_id()
                    item = newitem
        except steam.base.HttpError:
            return templates.error("Couldn't connect to Steam")
        except:
            return templates.item_error_notfound(iid)

        price = markup.generate_item_price_string(item, assets)

        return templates.item(user, item, item_outdated, price = price)

class live_item:
    """ More or less temporary until database stuff is sorted """
    def GET(self, user, iid):
        item_outdated = False
        cache = database.cache()
        try:
            user = cache.get_profile(user)
            items = cache.get_backpack(user)
            theitem = None
            for item in items:
                if item.get_id() == long(iid):
                    theitem = item
                    break
            if not theitem:
                return templates.item_error_notfound(iid)

            item = itemtools.process_attributes([theitem])[0]
            if web.input().get("contents"):
                itemcontents = item.optf2.get("contents")
                if itemcontents:
                    newitem = itemtools.process_attributes([itemcontents], gift = True)[0]
                    newitem.optf2 = dict(item.optf2, **newitem.optf2)
                    newitem.optf2["container_id"] = item.get_id()
                    item = newitem
        except steam.base.HttpError:
            return templates.error("Couldn't connect to Steam")
        except:
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
            items = cache.get_backpack(user)
            cell_count = items.get_total_cells()
            if not items and user.get_visibility() != 3:
                raise steam.user.ProfileError("Backpack is private")

            filter_classes = markup.sorted_class_list(itemtools.get_equippable_classes(items, cache))
            filter_qualities = itemtools.get_present_qualities(items)
            if sortclass:
                items = itemtools.filter_by_class(items, sortclass)
            if filter_quality:
                items = itemtools.filter_by_quality(items, filter_quality)

            items = itemtools.process_attributes(items)
            stats = itemtools.get_stats(items)

            sorted_items = itemtools.sort(items, sortby)
            baditems = []
            (items, baditems) = itemtools.build_page_object(sorted_items, ignore_position = (sortby != "cell"))

        except steam.items.Error as E:
            return templates.error("Failed to load backpack ({0})".format(E))
        except steam.user.ProfileError as E:
            return templates.error("Failed to load profile ({0})".format(E))
        except steam.base.HttpError as E:
            return templates.error("Couldn't connect to Steam (HTTP {0})".format(E))

        views = 0
        primary_group = user.get_primary_group()
        isvalve = False

        if primary_group:
            isvalve = int(primary_group) == config.ini.getint("steam", "valve-group-id")

        web.ctx.env["optf2_rss_url"] = markup.generate_mode_url("feed/" + str(user.get_id64()))
        web.ctx.env["optf2_rss_title"] = "{0}'s Backpack".format(user.get_persona().encode("utf-8"))

        price_stats = itemtools.get_price_stats(sorted_items, cache)
        return templates.inventory(user, isvalve, items, views,
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
            items = cache.get_backpack(user)
            items = itemtools.process_attributes(items)
            items = itemtools.sort(items, web.input().get("sort", "time"))

            return renderer.inventory_feed(user, items)

        except (steam.user.ProfileError, steam.items.Error, steam.base.HttpError) as E:
            return renderer.inventory_feed(None, [], erritem = E)

        except Exception as E:
            log.main.error(str(E))
            return renderer.inventory_feed(None, [], erritem = E)
