import steam, urllib2, json
import cPickle as pickle
from optf2.backend import database
from optf2.backend import items as itemtools
import web
import time
import config
import template
import api

templates = template.template

class loadout:
    """ User loadout lists """

    def GET(self, user):
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
    def GET(self, iid):
        schema = database.load_schema_cached(web.ctx.language)
        try:
            user = None
            item_outdated = False
            fromschema = False
            idl = iid.split('/')

            if len(idl) == 1:
                idl.append(idl[0])
            id64 = idl[1]

            try:
                theitem = schema[long(id64)]
                fromschema = True
            except:
                theitem = database.fetch_item_for_id(id64)

            if not fromschema:
                user = database.load_profile_cached(str(theitem["owner"]), stale = True)
                theitem = schema.create_item(theitem)
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
            return templates.item_error_notfound(id64)
        return templates.item(user, item, item_outdated)

class fetch:
    def _get_page_for_sid(self, sid):
        if not sid:
            return templates.error("Need an ID")
        try:
            user = database.load_profile_cached(sid)
        except urllib2.URLError:
            return templates.error("Couldn't connect to Steam")
        except steam.user.ProfileError as E:
            search = json.loads(api.search_profile().GET(sid))
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
            for ts in database.fetch_pack_for_user(user, tl_size = 20):
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

        except steam.items.Error as E:
            return templates.error("Failed to load backpack ({0})".format(E))
        except steam.user.ProfileError as E:
            return templates.error("Failed to load profile ({0})".format(E))
        except:
            return templates.error("Failed to load backpack")

        views = database.get_user_pack_views(user)
        isvalve = (user.get_primary_group() == config.valve_group_id)

        web.ctx.env["optf2_rss_url"] = "{0}feed/{1}".format(config.virtual_root, user.get_id64())
        web.ctx.env["optf2_rss_title"] = "{0}'s Backpack".format(user.get_persona().encode("utf-8"))

        return templates.inventory(user, isvalve, items, views,
                                   filter_classes, baditems,
                                   stats, timestamps, filter_qualities,
                                   total_pages)

    def GET(self, sid):
        return self._get_page_for_sid(sid)

class feed:
    def GET(self, sid):
        try:
            user = database.load_profile_cached(sid, stale = True)
            items = database.load_pack_cached(user)
            itemtools.process_attributes(items)
        except Exception as E:
            return templates.error(str(E))
        web.header("Content-Type", "application/rss+xml")
        return web.template.render(config.template_dir,
                                   globals = template.globals).inventory_feed(user, items)

