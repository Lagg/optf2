import web, config, steam, database, re
from copy import deepcopy

qualitydict = {"unique": "The",
               "normal": ""}

# I don't like this either but Valve didn't expose them
# through the API
particledict = {0: "Invalid Particle",
                1: "Particle 1",
                2: "Flying Bits",
                3: "Nemesis Burst",
                4: "Community Sparkle",
                5: "Holy Glow",
                6: "Green Confetti",
                7: "Purple Confetti",
                8: "Haunted Ghosts",
                9: "Green Energy",
                10: "Purple Energy",
                11: "Circling TF Logo",
                12: "Massed Flies",
                13: "Burning Flames",
                14: "Scorching Flames",
                15: "Searing Plasma",
                16: "Vivid Plasma",
                17: "Sunbeams",
                18: "Circling Peace Sign",
                19: "Circling Heart",
                20: "Map Stamps"}

def generate_full_item_name(item, ignore_qdict = False, strip_prefixes = False):
    """ Ignores the values in qualitydict if ignore_qdict is True """
    quality_str = item.get_quality()["str"]
    pretty_quality_str = item.get_quality()["prettystr"]
    custom_name = item.get_custom_name()
    item_name = item.get_name()

    if ignore_qdict:
        prefix = pretty_quality_str + " "
    else:
        prefix = qualitydict.get(quality_str, pretty_quality_str) + " "

    if item_name.find("The ") != -1 and item.is_name_prefixed():
        item_name = item_name[4:]

    if custom_name or (not item.is_name_prefixed() and quality_str == "unique"):
        prefix = ""
    if custom_name:
        item_name = custom_name

    item_name = web.websafe(item_name)

    if ((web.ctx.item_schema.get_language() != "en" and quality_str == "unique") or
        ignore_qdict and (quality_str == "unique" or quality_str == "normal") or
        strip_prefixes):
        return item_name
    else:
        return prefix + item_name

def absolute_url(relative_url):
    domain = web.ctx.homedomain
    if domain.endswith('/'): domain = domain[:-1]
    return domain + relative_url

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

def sort(items, sortby):
    if not items or len(items) == 0:
        return [None] * config.backpack_padded_size

    itemcmp = None
    def defcmp(x, y):
        if x < y:
            return -1
        elif x > y:
            return 1
        elif x == y:
            return 0

    if sortby == "time":
        items.reverse()

    if sortby == "serial":
        def itemcmp(x, y):
            return defcmp(x.get_id(),
                          y.get_id())
    elif sortby == "cell":
        def itemcmp(x, y):
            return defcmp(x.get_position(),
                          y.get_position())
    elif sortby == "level":
        def itemcmp(x, y):
            return defcmp(x.get_level(),
                          y.get_level())
    elif sortby == "name":
        def itemcmp(x, y):
            return defcmp(generate_full_item_name(x, strip_prefixes = True),
                          generate_full_item_name(y, strip_prefixes = True))
    elif sortby == "slot":
        def itemcmp(x, y):
            return defcmp(x.get_slot(), y.get_slot())
    elif sortby == "class":
        def itemcmp(x, y):
            cx = x.get_equipable_classes()
            cy = y.get_equipable_classes()
            lenx = len(cx)
            leny = len(cy)

            if lenx == 1 and leny == 1:
                return defcmp(cx[0], cy[0])
            else:
                return defcmp(lenx, leny)

    if itemcmp:
        items.sort(cmp = itemcmp)

    itemcount = len(items)
    highestpos = items[-1].get_position()

    if itemcount < config.backpack_padded_size:
        itemcount = config.backpack_padded_size

    if sortby == "cell" and highestpos > itemcount:
        itemcount = highestpos

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


def process_attributes(items):
    """ Filters attributes for the item list,
    optf2-specific data is stored in item.optf2 """

    newitems = []
    for item in items:
        if not item: continue
        if not getattr(item, "optf2", None):
            item.optf2 = {}
        attrs = item.get_attributes()
        item.optf2["attrs"] = []
        item.optf2["description"] = item.get_description()
        item.optf2["image_url"] = item.get_image(item.ITEM_IMAGE_SMALL)
        item.optf2["image_url_large"] = item.get_image(item.ITEM_IMAGE_LARGE)
        min_level = item.get_min_level()
        max_level = item.get_max_level()
        pb_level = item.get_level()
        custom_desc = item.get_custom_description()
        itype = item.get_type()

        if itype.startswith("TF_"):
            s1 = re.sub("(.)([A-Z][a-z]+)", "\\1 \\2", itype[3:])
            itype = re.sub("([a-z0-9])([A-Z])", "\\1 \\2", s1)
            itype = itype.replace("_", "")
        item.optf2["type"] = itype

        if custom_desc: item.optf2["description"] = custom_desc

        if min_level == max_level:
            item.optf2["level"] = str(min_level)
        else:
            item.optf2["level"] = str(min_level) + "-" + str(max_level)

        if pb_level != None: item.optf2["level"] = pb_level

        for theattr in attrs:
            newattr = deepcopy(theattr)
            desc = newattr.get_description()

            # Contained item is a schema id, this is an incredibly
            # ugly hack but I'm too stubborn to make DB changes for this
            if newattr.get_name() == "referenced item def":
                giftcontents = newattr.get_value()

                if not isinstance(giftcontents, dict):
                    giftcontents = item._schema[(int(giftcontents))]
                else:
                    giftcontents = steam.tf2.item(item._schema, giftcontents)

                giftcontents.optf2 = {}
                giftcontents.optf2["gift_container_id"] = item.get_id()
                item.optf2["gift_content"] = generate_full_item_name(giftcontents)
                item.optf2["gift_quality"] = giftcontents.get_quality()["str"]
                item.optf2["gift_item"] = giftcontents

                newattr._attribute["description_string"] = 'Contains ' + item.optf2["gift_content"]
                newattr._attribute["hidden"] = False

            if newattr.get_name() == "set item tint RGB":
                raw_rgb = int(newattr.get_value())

                if raw_rgb == 1:
                    # Team Spirit
                    item_color = 'url("{0}team_splotch.png")'.format(config.static_prefix)
                else:
                    item_color = "#{0:02X}{1:02X}{2:02X}".format((raw_rgb >> 16) & 0xFF,
                                                                 (raw_rgb >> 8) & 0xFF,
                                                                 (raw_rgb) & 0xFF)

                # Workaround until the icons for colored paint cans are correct
                try:
                    schema_paintcan = item._schema[item.get_schema_id()]
                except KeyError: schema_paintcan = 0
                if (schema_paintcan and
                    schema_paintcan._item.get("name", "").startswith("Paint Can") and
                    raw_rgb != 0 and raw_rgb != 1):
                    paintcan_url = "{0}item_icons/Paint_Can_{1}.png".format(config.static_prefix,
                                                                            item_color[1:])
                    item.optf2["image_url"] = absolute_url(paintcan_url)
                    item.optf2["image_url_large"] = absolute_url(paintcan_url)
                item.optf2["color"] = item_color
                continue

            if newattr.get_name() == "attach particle effect":
                newattr._attribute["description_string"] = ("Effect: " +
                                                            particledict.get(int(newattr.get_value()), particledict[0]))

            if newattr.get_name() == "gifter account id":
                newattr._attribute["description_string"] = "Gift"
                item.optf2["gift_from"] = "7656" + str(int(newattr.get_value()) +
                                                       1197960265728)
                try:
                    user = database.load_profile_cached(item.optf2["gift_from"], stale = True)
                    item.optf2["gift_from_persona"] = user.get_persona()
                    newattr._attribute["description_string"] = "Gift from " + item.optf2["gift_from_persona"]
                except:
                    item.optf2["gift_from_persona"] = "this user"

            if not newattr.is_hidden():
                newattr._attribute["description_string"] = web.websafe(newattr.get_description())
            else:
                continue

            item.optf2["attrs"].append(newattr)

        if "gift_item" in item.optf2:
            item.optf2["gift_item"].optf2["gift_from_persona"] = item.optf2["gift_from_persona"]
            item.optf2["gift_item"].optf2["gift_from"] = item.optf2["gift_from"]

        quality_str = item.get_quality()["str"]
        full_qdict_name = generate_full_item_name(item)
        full_default_name = generate_full_item_name(item, True)
        is_gift_contents = "gift_container_id" in item.optf2

        item.optf2["cell_name"] = '<div class="prefix-{0} item-name">{1}</div>'.format(quality_str, full_qdict_name)

        color = item.optf2.get("color")
        paint_job = ""
        prefix = ""
        if color:
            if color.startswith("url"):
                color = "#FF00FF"
                paint_job = '<span><b style="color: #B8383B;">Pain</b><b style="color: #5885A2;">ted</b></span>'
            else:
                paint_job = '<span style="color: {0}; font-weight: bold;">Painted</span>'.format(color)
        if is_gift_contents:
            prefix = '<span class="prefix-giftwrapped">Giftwrapped</span>'
        item.optf2["painted_text"] = paint_job
        item.optf2["dedicated_name"] = "{0} {1} {2}".format(prefix, paint_job, full_default_name)

        if color:
            paint_job = "Painted"
        if is_gift_contents:
            prefix = "Giftwrapped"
        item.optf2["title_name"] = "{0} {1} {2}".format(prefix, paint_job, full_default_name)

        if color:
            paint_job = "(Painted)"
        else:
            paint_job = ""
        item.optf2["feed_name"] = "{0} {1}".format(full_qdict_name, paint_job)

        newitems.append(item)

    items = newitems
    return newitems

def get_equippable_classes(items):
    """ Returns a set of classes that can equip this
    item """

    valid_classes = set()

    if not items: return []

    for item in items:
        if not item: continue
        classes = item.get_equipable_classes()
        valid_classes |= set(classes)

    return sorted(list(valid_classes))

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
