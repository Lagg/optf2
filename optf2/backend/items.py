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

import web, config, steam, database, re, operator, time
from optf2.frontend.markup import absolute_url

qualitydict = {"unique": "The",
               "normal": ""}

# Capability string mapping, this will probably need localizing too
capabilitydict = {"can_gift_wrap": "Gift wrappable",
                  "can_craft_count": "Can be a numbered craft",
                  "decodable": "Opened via key",
                  "usable": "Action item",
                  "usable_gc": "Usable outside Action slot",
                  "usable_out_of_game": "Usable out of game",
                  "can_craft_mark": "Holds crafter name",
                  "nameable": "Nameable",
                  "paintable": "Paintable"}

def _(thestring):
    return thestring.encode("utf-8")

gamelib = getattr(steam, config.game_mode)

def get_invalid_pos(items):
    poslist = []
    invalid_items = []
    for item in items:
        if not item: continue
        pos = item.get_position()
        if pos != -1 and pos not in poslist:
            poslist.append(item.get_position())
        else:
            invalid_items.append(item)

    return invalid_items

def condensed_to_id64(value):
    return "7656" + str(int(value) + 1197960265728)

def sort(items, sortby):
    if not items:
        return [None] * config.backpack_padded_size

    items = list(items)
    itemcmp = None

    if sortby == "serial" or sortby == "time":
        itemcmp = operator.methodcaller("get_id")
    elif sortby == "cell":
        itemcmp = operator.methodcaller("get_position")
    elif sortby == "level":
        def levelcmp(obj):
            level = obj.get_level()

            if not level:
                level = obj.get_min_level()
                levelmax = obj.get_max_level()
                if level != levelmax: level = levelmax - level

            return level
        itemcmp = lambda obj: levelcmp(obj)
    elif sortby == "name":
        itemcmp = lambda obj: obj.get_full_item_name(prefixes = None)
    elif sortby == "slot":
        itemcmp = operator.methodcaller("get_slot")
    elif sortby == "class":
        def classcmp(obj):
            eq = obj.get_equipable_classes()
            eqlen = len(eq)

            if eqlen == 1:
                return eq[0]
            else:
                return eqlen
        itemcmp = lambda obj: classcmp(obj)
    elif sortby == "schemaid":
        itemcmp = operator.methodcaller("get_schema_id")

    if itemcmp:
        items.sort(key = itemcmp)

    itemcount = len(items)
    highestpos = items[-1].get_position()

    if itemcount < config.backpack_padded_size:
        itemcount = config.backpack_padded_size

    if sortby == "cell" and highestpos > itemcount:
        itemcount = highestpos

    if sortby == "time":
        items.reverse()

    rem = itemcount % 50
    if rem != 0: itemcount += (50 - rem)
    pagecount = itemcount / 50

    if sortby == "cell":
        newitems = [None] * (itemcount + 1)
        for item in items:
            pos = item.get_position()
            try:
                if pos > -1 and newitems[pos] == None:
                    newitems[pos] = item
            except IndexError: pass
        del newitems[0]
        return newitems

    return items + ([None] * (itemcount - len(items)))

def filter_by_class(items, theclass):
    filtered_items = []

    for item in items:
        if not item: continue
        classes = item.get_equipable_classes()
        for c in classes:
            if c == theclass:
                filtered_items.append(item)
                break
    return filtered_items

def filter_by_quality(items, thequality):
    filtered_items = []

    for item in items:
        if not item: continue
        if str(item.get_quality()["id"]) == thequality:
            filtered_items.append(item)
    return filtered_items

def get_stats(items):
    """ Returns a dict of various backpack stats """
    stats = {"weapons": 0,
             "misc": 0,
             "hats": 0,
             "total": 0}

    for item in items:
        if not item: continue

        slot = item.get_slot()
        iclass = item.get_class()

        stats["total"] += 1

        if slot == "primary" or slot == "melee" or slot == "secondary":
            if iclass.find("token") == -1:
                stats["weapons"] += 1
        elif slot == "head" and iclass.find("token") == -1:
            stats["hats"] += 1
        elif slot == "misc":
            stats["misc"] += 1
    return stats


def process_attributes(items, gift = False):
    """ Filters attributes for the item list,
    optf2-specific data is stored in item.optf2 """

    default_item_image = config.static_prefix + "item_icons/Invalid_icon.png";
    newitems = []
    schema = database.load_schema_cached(web.ctx.language)
    loaded_profiles = {}

    for item in items:
        if not item: continue
        if not getattr(item, "optf2", None):
            item.optf2 = {}
        attrs = item.get_attributes()
        item.optf2["attrs"] = []
        item.optf2["description"] = item.get_description()
        item.optf2["image_url"] = item.get_image(item.ITEM_IMAGE_SMALL) or default_item_image
        item.optf2["image_url_large"] = item.get_image(item.ITEM_IMAGE_LARGE) or default_item_image
        item.optf2["rank_name"] = ""
        min_level = item.get_min_level()
        max_level = item.get_max_level()
        pb_level = item.get_level()
        custom_desc = item.get_custom_description()
        giftcontents = item.get_contents()
        killtypestrings = schema.get_kill_types()
        defaulttype = killtypestrings.get(0, "Broken")

        item.optf2["kill_type"] = defaulttype
        item.optf2["kill_type_2"] = defaulttype

        itype = item.get_type()
        if itype.startswith("TF_"): itype = ""
        item.optf2["type"] = itype

        if custom_desc: item.optf2["description"] = custom_desc

        if min_level == max_level:
            item.optf2["level"] = str(min_level)
        else:
            item.optf2["level"] = str(min_level) + "-" + str(max_level)

        if pb_level != None: item.optf2["level"] = pb_level

        for theattr in attrs:
            newattr = {}
            attrname = theattr.get_name()

            if attrname == "referenced item def":
                if not giftcontents:
                    giftcontents = schema[int(theattr.get_value())]
                newattr["description_string"] = 'Contains ' + giftcontents.get_full_item_name(prefixes = qualitydict)
                newattr["hidden"] = False

            if (attrname == "set item tint RGB" or
                attrname == "set item tint RGB 2"):
                raw_rgb = int(theattr.get_value())
                secondary_color = attrname.endswith("2")

                # Workaround for Team Spirit values still being 1
                if raw_rgb == 1:
                    raw_rgb = 12073019
                    item.optf2["color_2"] = "#256D8D"

                item_color = "#{0:02X}{1:02X}{2:02X}".format((raw_rgb >> 16) & 0xFF,
                                                             (raw_rgb >> 8) & 0xFF,
                                                             (raw_rgb) & 0xFF)

                try: paint_can = schema[schema.optf2_paints.get(raw_rgb)]
                except KeyError: paint_can = None
                if paint_can: item.optf2["paint_name"] = paint_can.get_name()
                elif "paint_name" not in item.optf2: item.optf2["paint_name"] = "unknown paint"

                # Workaround until the icons for colored paint cans are correct
                if (not secondary_color and
                    item._schema_item.get("name", "").startswith("Paint Can") and
                    raw_rgb != 0):
                    paintcan_url = "{0}item_icons/Paint_Can_{1}.png".format(config.static_prefix,
                                                                            item_color[1:])
                    item.optf2["image_url"] = absolute_url(paintcan_url)
                    item.optf2["image_url_large"] = absolute_url(paintcan_url)

                if secondary_color:
                    item.optf2["color_2"] = item_color
                else:
                    item.optf2["color"] = item_color
                continue

            if attrname == "attach particle effect":
                particles = schema.get_particle_systems()
                particleid = int(theattr.get_value())
                particlename = particles.get(particleid)
                if particlename: particlename = particlename["name"]
                else: particlename = str(particleid)
                newattr["description_string"] = ("Effect: " + particlename)
                item.optf2["particle-id"] = particleid

            if attrname == "gifter account id":
                newattr["description_string"] = "Gift"
                item.optf2["gifter_id"] = condensed_to_id64(theattr.get_value())

                try:
                    gifter = item.optf2["gifter_id"]
                    if gifter not in loaded_profiles:
                        user = database.load_profile_cached(gifter, stale = True)
                        loaded_profiles[gifter] = user
                    else:
                        user = loaded_profiles[gifter]

                    item.optf2["gifter_persona"] = user.get_persona()
                    newattr["description_string"] = "Gift from " + item.optf2["gifter_persona"]
                except:
                    item.optf2["gifter_persona"] = "this user"

            if attrname == "makers mark id":
                crafter_id64 = condensed_to_id64(theattr.get_value())

                try:
                    if crafter_id64 not in loaded_profiles:
                        user = database.load_profile_cached(crafter_id64, stale = True)
                        loaded_profiles[crafter_id64] = user
                    else:
                        user = loaded_profiles[crafter_id64]
                    item.optf2["crafted_by_persona"] = user.get_persona()
                except:
                    item.optf2["crafted_by_persona"] = "this user"

                item.optf2["crafted_by_id64"] = crafter_id64
                newattr["description_string"] = "Crafted by " + item.optf2["crafted_by_persona"]
                newattr["hidden"] = False

            if attrname == "unique craft index":
                item.optf2["craft_number"] = str(int(theattr.get_value()))

            if attrname == "tradable after date":
                # WORKAROUND: For some reason this has the wrong type and is hidden,
                # not sure if this should be in steamodd or not
                d = time.gmtime(theattr.get_value())
                item.optf2["date_tradable"] = time.strftime("%F %H:%M:%S", d)

            if attrname == "kill eater":
                item.optf2["kill_count"] = int(theattr.get_value())

            if attrname == "kill eater 2":
                item.optf2["kill_count_2"] = int(theattr.get_value())

            if attrname == "kill eater score type":
                item.optf2["kill_type"] = killtypestrings.get(int(theattr.get_value()), defaulttype)
            if attrname == "kill eater score type 2":
                item.optf2["kill_type_2"] = killtypestrings.get(int(theattr.get_value()), defaulttype)

            if attrname == "unlimited quantity":
                item._item["quantity"] = 1

            if "kill_count" in item.optf2:
                kill_count = item.optf2["kill_count"]
                kill_count_2 = item.optf2.get("kill_count_2")
                for rank in schema.get_kill_ranks():
                    item.optf2["rank_name"] = rank["name"]
                    if ((kill_count and kill_count < rank["required_score"]) or
                        (kill_count_2 and kill_count_2 < rank["required_score"])):
                        break

            if not newattr.get("hidden", theattr.is_hidden()):
                newattr["description_string"] = web.websafe(newattr.get("description_string",
                                                                        theattr.get_description()))
            else:
                continue

            item.optf2["attrs"].append(steam.items.item_attribute(dict(theattr._attribute.items() + newattr.items())))

        caps = item.get_capabilities()
        if caps:
            item.optf2["capabilities"] = [capabilitydict.get(cap, cap) for cap in caps]

        if giftcontents:
            item.optf2["contents"] = giftcontents
            item.optf2["content_string"] = ('Contains <span class="prefix-{0}">{1}</span>').format(giftcontents.get_quality()["str"],
                                                                                                   giftcontents.get_full_item_name(prefixes = qualitydict))

        quality_str = item.get_quality()["str"]
        full_qdict_name = item.get_full_item_name(prefixes = qualitydict)
        full_default_name = item.get_full_item_name({"normal": None, "unique": None})
        color = item.optf2.get("color")
        color_2 = item.optf2.get("color_2")
        paint_job = ""
        prefix = ""

        if color and color_2:
            paint_job = '<span><b style="color: {0};">Pain</b><b style="color: {1};">ted</b></span>'.format(color,
                                                                                                            color_2)
        elif color:
            paint_job = '<span style="color: {0}; font-weight: bold;">Painted</span>'.format(color)

        if gift:
            prefix = '<span class="prefix-giftwrapped">Giftwrapped</span>'

        item.optf2["painted_text"] = paint_job
        item.optf2["dedicated_name"] = "{0} {1}".format(_(prefix), _(full_default_name))

        item.optf2["cell_name"] = '<div class="prefix-{0} item-name">{1}</div>'.format(_(quality_str),
                                                                                       _(full_qdict_name))

        if color:
            paint_job = "Painted"
        if gift:
            prefix = "Giftwrapped"
        item.optf2["title_name"] = "{0} {1} {2}".format(_(prefix), _(paint_job), _(full_default_name))

        if color:
            paint_job = "(Painted)"
        else:
            paint_job = ""
        item.optf2["feed_name"] = "{0} {1}".format(_(full_qdict_name), _(paint_job))

        levelprefix = "Level " + str(item.optf2["level"]) + " "
        if item.optf2["rank_name"]:
            levelprefix = ""
        item.optf2["level_string"] = '<div class="item-level">{0}{1} {2}</div>'.format(levelprefix,
                                                                                       item.optf2["rank_name"],
                                                                                       item.optf2["type"].encode("utf-8"))

        newitems.append(item)

    return newitems

def get_equippable_classes(items):
    """ Returns a set of classes that can equip the listed items """

    valid_classes = set()
    schema = database.load_schema_cached(web.ctx.language)

    if not items: return []

    for item in items:
        if not item: continue
        classes = item.get_equipable_classes()
        valid_classes |= set(classes)

    ordered_classes = list(schema.class_bits.values())
    for c in ordered_classes:
        if c not in valid_classes:
            del c

    return ordered_classes

def _quality_sort(x, y):
    px = x["prettystr"]
    py = y["prettystr"]

    if px < py: return -1
    elif px > py: return 1
    else: return 0

def get_present_qualities(items):
    """ Returns a sorted list of qualities that are in this set
    of items """

    qualities = set()
    qlist = []

    for item in items:
        if not item: continue
        quality = item.get_quality()
        if quality["id"] not in qualities:
            qualities.add(quality["id"])
            qlist.append(quality)

    qlist.sort(cmp = _quality_sort)
    return qlist

def get_present_capabilities(items):
    """ Returns a sorted list of capabilities in this set of items,
    uses the capabilitydict """

    caps = set()

    for item in items:
        if not item: continue
        caps |= set(item.get_capabilities())

    caplist = [{"name": capabilitydict.get(cap, cap), "flag": cap} for cap in caps]
    caplist.sort(key = operator.itemgetter("name"))
    return caplist

def filter_by_capability(items, capability):

    if not items: return []

    filtered = []
    for item in items:
        if not item: continue
        if capability in item.get_capabilities():
            filtered.append(item)

    return filtered
