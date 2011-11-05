import steam, urllib2
import cPickle as pickle
from optf2.backend import database
from optf2.backend import items as itemtools
from optf2.frontend.markup import generate_mode_url
import web
import time
import config
import template

templates = template.template

class loadout:
    """ User loadout lists """

    def GET(self, game, user):
        web.ctx.current_game = game
        try:
            userp = database.load_profile_cached(user)
            items = database.load_pack_cached(userp)
            equippeditems = {}
            schema = database.load_schema_cached(web.ctx.language)
            valid_classes = schema.class_bits.values()
            slotlist = ["Head", "Misc", "Primary", "Secondary", "Melee", "Pda", "Pda2", "Building", "Action"]

            normalitems = itemtools.filter_by_quality(schema, "0")
            for item in normalitems:
                classes = item.get_equipable_classes()
                for c in classes:
                    if c not in equippeditems:
                        equippeditems[c] = {}

                    slot = item.get_slot().title()
                    if slot not in slotlist: slotlist.append(slot)
                    if slot not in equippeditems[c]:
                        equippeditems[c][slot] = []

                    equippeditems[c][slot].append(itemtools.process_attributes([item])[0])

            for item in items:
                classes = item.get_equipped_classes()
                for c in classes:
                    if c not in equippeditems: equippeditems[c] = {}
                    # WORKAROUND: There is one unique shotgun for all classes, and it's in the primary slot. This
                    # has obvious problems
                    if item.get_schema_id() == 199 and c != "Engineer":
                        slot = "Secondary"
                    else:
                        slot = item.get_slot().title()
                    if slot not in slotlist: slotlist.append(slot)
                    if slot not in equippeditems[c] or equippeditems[c][slot][0].get_quality()["id"] == 0:
                        equippeditems[c][slot] = []
                    equippeditems[c][slot].append(itemtools.process_attributes([item])[0])

            return templates.loadout(userp, equippeditems, valid_classes, slotlist)
        except steam.items.Error as E:
            return templates.error("Backpack error: {0}".format(E))
        except steam.user.ProfileError as E:
            return templates.error("Profile error: {0}".format(E))
        except:
            return templates.error("Couldn't load loadout page")

class item:
    def GET(self, app, iid):
        web.ctx.current_game = app
        schema = database.load_schema_cached(web.ctx.language)
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
        except urllib2.URLError:
            return templates.error("Couldn't connect to Steam")
        except:
            return templates.item_error_notfound(iid)
        return templates.item(user, item, item_outdated)

class fetch:
    def GET(self, game, sid):
        web.ctx.current_game = game
        sid = sid.strip('/').split('/')
        if len(sid) > 0: sid = sid[-1]

        if not sid:
            return templates.error("Need an ID")
        try:
            user = database.load_profile_cached(sid)
        except urllib2.URLError:
            return templates.error("Couldn't connect to Steam")
        except steam.user.ProfileError as E:
            return templates.error(E)

        query = web.input()
        sortby = query.get("sort", "cell")
        sortclass = query.get("sortclass")
        packid = query.get("pid")
        filter_quality = query.get("quality")

        try:
            items = database.load_pack_cached(user, pid = packid)
            if not items and user.get_visibility() != 3:
                raise steam.user.ProfileError("Backpack is private")

            filter_classes = itemtools.get_equippable_classes(items)
            filter_qualities = itemtools.get_present_qualities(items)
            if sortclass:
                items = itemtools.filter_by_class(items, sortclass)
            if filter_quality:
                items = itemtools.filter_by_quality(items, filter_quality)

            items = itemtools.process_attributes(items)
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

        except steam.items.Error as E:
            return templates.error("Failed to load backpack ({0})".format(E))
        except steam.user.ProfileError as E:
            return templates.error("Failed to load profile ({0})".format(E))
        except:
            return templates.error("Failed to load backpack")

        views = database.get_user_pack_views(user)
        isvalve = (user.get_primary_group() == config.valve_group_id)
        schema = database.load_schema_cached(web.ctx.language)

        web.ctx.env["optf2_rss_url"] = generate_mode_url("feed/" + str(user.get_id64()))
        web.ctx.env["optf2_rss_title"] = "{0}'s Backpack".format(user.get_persona().encode("utf-8"))

        return templates.inventory(user, isvalve, items, views,
                                   filter_classes, baditems,
                                   stats, filter_qualities,
                                   total_pages, schema._app_id)

class feed:
    def GET(self, game, sid):
        web.ctx.current_game = game
        try:
            user = database.load_profile_cached(sid, stale = True)
            items = database.load_pack_cached(user)
            items = itemtools.process_attributes(items)
            items = itemtools.sort(items, web.input().get("sort", "time"))
        except Exception as E:
            return templates.error(str(E))
        web.header("Content-Type", "application/rss+xml")
        return web.template.render(config.template_dir,
                                   globals = template.globals).inventory_feed(user, items)

