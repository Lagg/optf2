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

import web
import re
import operator
from os.path import join as pathjoin
try: from collections import OrderedDict as odict
except ImportError: odict = dict
from urlparse import urljoin
from optf2 import config, log

virtual_root = config.ini.get("resources", "virtual-root")
static_prefix = config.ini.get("resources", "static-prefix")
particles = dict(config.ini.items("particle-modes"))
cssaliases = dict(config.ini.items("css-aliases"))
app_aliases = dict(config.ini.items("app-aliases"))
# TODO: Add exp for single tags like br
htmldesc = re.compile("<(?P<tag>.+) ?.*>.+</(?P=tag)>")

celldims = {}
for mode, dims in config.ini.items("page-dimensions"):
    sep = dims.lower().find('x')
    if sep == -1:
        val = int(dims)
        celldims[mode] = {"width": val, "height": val}
    else:
        celldims[mode] = {"width": int(dims[:sep]), "height": int(dims[sep + 1:])}

# Capability string mapping, this will probably need localizing too
capabilitydict = {"can_gift_wrap": "Gift wrappable",
                  "can_craft_count": "Can be a numbered craft",
                  "decodable": "Opened via key",
                  "usable": "Action item",
                  "usable_gc": "Usable outside Action slot",
                  "usable_out_of_game": "Usable out of game",
                  "can_craft_mark": "Holds crafter name",
                  "nameable": "Nameable",
                  "paintable": "Paintable",
                  "can_be_restored": "Restorable",
                  "can_customize_texture": "Allows custom texture",
                  "strange_parts": "Allows Strange parts",
                  "paintable_unusual": "Allows Unusual paints"}

classoverrides = {
    "440": odict([
            (1, "Scout"),
            (3, "Soldier"),
            (7, "Pyro"),
            (4, "Demoman"),
            (6, "Heavy"),
            (9, "Engineer"),
            (5, "Medic"),
            (2, "Sniper"),
            (8, "Spy")
            ]),
    "620": odict([
            (1, "P-body"),
            (2, "Atlas")
            ]),
    "570": {
        1000: "Multi-hero"
        }
    }
overridealiases = {
    "520": "440",
    "205790": "570"
}
reverrides = {}
for k, v in classoverrides.iteritems(): reverrides[k + "_swap"] = dict(zip(v.values(), v.keys()))
classoverrides.update(reverrides)

def get_class_for_id(cid, ident):
    ident = str(ident)
    overrides, swapped_overrides = get_class_overrides(ident)
    try: realcid = int(cid)
    except ValueError: realcid = str(cid)

    if not overrides: return realcid, cid

    if realcid in overrides:
        return (realcid, overrides[realcid])
    elif realcid in swapped_overrides:
        return (swapped_overrides[realcid], cid)
    else:
        return (realcid, cid)

def get_class_overrides(ident):
    ident = str(ident)
    ident = overridealiases.get(ident, ident)

    if ident not in classoverrides: return {}, {}

    return (classoverrides.get(ident),
            reverrides.get(ident + "_swap"))

def sorted_class_list(classes, app = None):
    validclasses = [get_class_for_id(c, app) for c in classes]

    return sorted(validclasses, key = operator.itemgetter(1))

def get_page_sizes():
    return celldims

def get_capability_strings(caps):
    """ Returns a list of tuples containing
    (capname, capid) where capname
    is the pretty version in the capabilitydict
    if available """

    return sorted([(capabilitydict.get(cap, cap), cap) for cap in caps])

def get_quality_strings(q, schema):
    try:
        qmap = schema.qualities
        return sorted([(qmap.get(k, k), k) for k in q])
    except:
        return {}

def absolute_url(relative_url):
    return urljoin(web.ctx.homedomain, relative_url)

def generate_root_url(path = "", subroot = ""):
    """ Generate a URL beginning with the virtual root value,
    followed by an optional sub-root, then the path """

    return pathjoin(virtual_root, str(subroot), str(path))

def set_navlink(path = "", override = False):
    """ Note: Assumes the first part of the URL is the mode """

    try:
        path = (path or web.ctx.path).lstrip('/')
        slash = path.find('/')

        if override:
            web.ctx["navlink"] = path
        elif slash != -1:
            web.ctx["navlink"] = path[slash + 1:]
    except:
        pass

def init_theme(theme):
    theme = str(theme)
    theme = app_aliases.get(theme, theme)
    web.ctx.setdefault("css_extra", [])
    web.ctx.css_extra.append(pathjoin(static_prefix, "theme", cssaliases.get(theme, theme) + ".css"))
    dims = get_page_sizes()
    web.ctx._cvars["cellsPerRow"] = dims.get(theme, dims["default"])["width"]

def generate_particle_icon_url(pid, ident):
    ident = str(ident)
    ident = app_aliases.get(ident, ident)

    return static_prefix + "particles/" + particles.get(ident, ident) + '/' + str(pid) + ".png"

def generate_item_description(item):
    desc = item.get("desc", '')
    custom = item.get("cdesc")
    output = web.websafe(desc)

    if custom or not htmldesc.search(desc):
        output = web.websafe(desc)
    else:
        output = desc

    if output: return '<div class="item-description">' + output.replace('\n', '<br/>') + '</div>'
    else: return ''

def generate_item_type_line(item, classic = True):
    """ If classic is true the full Level X Y
    formatting will be used, if not only the type and other relevant information
    will be """

    origin_name = ""
    levelprefix = ""
    rank = item.get("rank", "")
    itemorigin = item.get("origin")
    level = item.get("level")
    itype = item.get("type", "")
    limited = item.get("limited")

    if classic and level:
        levelprefix = "Level {0}".format(level)

    if limited:
        levelprefix = "Limited " + levelprefix

    if itemorigin:
        origin_name = " - " + itemorigin

    # Add space to prefix for rank
    if rank: levelprefix += ' '

    return u'<div class="item-level">{0}{1} {2}{3}</div>'.format(levelprefix,
                                                                 web.websafe(rank),
                                                                 web.websafe(itype),
                                                                 web.websafe(origin_name))


def generate_item_url(app, item, user = None):
    """ Intelligently generates a URL linking to
    the given item """

    itemid = item.get("id")
    pathuser = ""

    if itemid and user:
        try: pathuser = str(user["id64"])
        except: pathuser = str(user)

    if pathuser: pathuser += "/"

    return generate_root_url("item/" + pathuser + str(itemid or item["sid"]), app)

def generate_item_paint_line(item):
    """ Returns a "Painted with X" line if available """

    colors = item.get("colors", [])
    colorslen = len(colors)
    painted = "Painted"

    if colorslen > 1:
        painted = '<span><b style="color: {0[0][1]};">Pain</b><b style="color: {0[1][1]};">ted</b></span>'.format(colors)
    elif colorslen > 0:
        painted = '<span style="color: {0[0][1]}; font-weight: bold;">Painted</span>'.format(colors)

    paintcan = item.get("paint_name")
    if paintcan:
        return u'<div class="attr-positive">{0} with {1}</div>'.format(painted, web.websafe(paintcan))
    else:
        return u''

def generate_item_price_string(item, stats):
    assets = None

    if not stats: return None

    if "assets" in stats: assets = stats["assets"]
    else: assets = stats

    try: return "Store price: ${0}".format(assets[str(item["sid"])]["USD"])
    except: return None

def generate_attribute_list(app, item, showlinks = False):
    contents = item.get("contents")
    markup = []
    list_open = u'<ul class="attribute-list">'
    list_close = u'</ul>'
    eater_fmt = u'<li class="attr-positive">{0}</li>'
    morestr = ''

    if showlinks:
        morestr = ' <a href="{0}">(more)</a>'

    for attr in item.get("attrs", []):
        desc = attr.get("desc", '').strip('\n')
        style = ""
        acct = item.get("accounts", {}).get(str(attr["id"]))
        color = attr.get("color")
        atype = attr.get("type", "neutral")

        if "name" not in attr:
            continue

        aid = attr["id"]
        name = attr["name"]
        val = attr["val_raw"]
        try:
            if (float(val).is_integer()):
                val = "{0:d}".format(int(val))
            else:
                val = "{0:.3g}".format(val)
        except ValueError:
            pass

        debug = int(web.input(debug=0).debug)

        if not desc and not debug:
            continue

        if color:
            style = ' style="color: #{0};"'.format(color)

        markup.append('<li class="attr-{0}"{1}>'.format(atype, style))

        # TODO: This is getting increasingly ugly
        # 194 == referenced item def
        # 192 == referenced item id low
        # 193 == referenced item id high
        if desc:
            if contents and (aid == 194 or aid == 192 or aid == 193):
                markup.append(desc + morestr.format(web.http.changequery(contents = 1)))
            else:
                if atype != "html": desc = web.websafe(desc)
                markup.append(desc.replace('\n', "<br/>"))

        if name and aid and debug:
            if desc:
                markup.append('<br/>')
            markup.append('{} ({}): {}'.format(web.websafe(name), aid, val))

        if acct:
            markup.append(morestr.format(generate_root_url("user/"  + str(acct["id64"]), app)))

        markup.append('</li>')

    markup += map(eater_fmt.format, item.get("eaters", []))

    # current style
    style = item.get("style")
    if style:
        markup.append('<li class="attr-neutral">Style: {0}</li>'.format(style))

    # available styles
    styles = item.get("styles")
    if styles:
        markup.append(u'<li class="attr-neutral">Styles: {0}</li>'.format(', '.join(styles)))

    quantity = item.get("qty")
    if quantity:
        markup.append('<li class="attr-neutral">Quantity: {0}</li>'.format(quantity))

    if not item.get("tradable"):
        markup.append('<li class="attr-negative">Untradable</li>')

    if not item.get("craftable"):
        markup.append('<li class="attr-negative">Uncraftable</li>')

    if not markup:
        return u''
    else:
        return (list_open + u''.join(markup) + list_close)


def generate_item_cell(app, item, invalid = False, show_equipped = True, user = None, pricestats = None):
    if not item:
        return u'<div class="item_cell"></div>'

    itemid = item.get("id")
    schema_item = False
    equipped = show_equipped and (len(item.get("equipped", {})) > 0)

    if not itemid:
        schema_item = True
        itemid = item["sid"]

    item_link = generate_item_url(app, item, user)
    quality = item.get("quality", "normal")
    equippedstr = ""
    quantity = item.get("qty")
    cell_class = "item_cell"

    if not schema_item and item.get("pos", -1) <= -1:
        cell_class += " undropped"

    style = ""
    coloroverride = item.get("namergb")

    if coloroverride:
        style = 'border-color: #{0};'.format(coloroverride)

    pid = item.get("pid")

    if pid != None:
        pid = ",url('{0}')".format(generate_particle_icon_url(pid, app))
    else:
        pid = ''

    markup = [(u'<div class="{0} cell-{1}" id="s{2}" style="background-image: url(\'{6[image]}\'){5};{4}">' +
               '<a class="item-link" href="{3}">' +
               '</a>'
              ).format(cell_class, quality, itemid, item_link, style, pid, item)]

    contents = item.get("contents")
    series = item.get("series")
    craftno = item.get("craftno")
    texture = item.get("texture")

    if contents:
        markup.append('<img src="' + contents["image"] + '" alt="0" class="item-image gift-preview"/>')

    ctop = []

    if item.get("cname"):
        ctop.append('<img src="' + static_prefix + 'name_tag.png" alt="Named"/>')

    if item.get("cdesc"):
        ctop.append('<img src="' + static_prefix + 'desc_tag.png" alt="Described"/>')

    if "gifter" in item:
        ctop.append('<img src="' + static_prefix + 'gift_icon.png" alt="Gift"/>')

    if ctop:
        markup.append('<div class="cell-top">')
        markup += ctop
        markup.append('</div>')

    for cid, color in item.get("colors", []):
        sec = ''
        if cid != 0: sec = " secondary"
        markup.append('<span class="paint_splotch{0}" style="background-color: {1};"></span>'.format(sec, color))

    if series:
        markup.append('<span class="crate-series-icon">{0}</span>'.format(series))

    if craftno:
        markup.append('<div class="craft-number-icon">{0}</div>'.format(craftno))

    if texture:
        markup.append('<img class="icon-custom-texture"  src="' + texture + '" alt="texture"/>')

    cbottom = []

    if equipped:
        cbottom.append('<span class="ui-icon ui-icon-suitcase"></span>')

    if quantity:
        cbottom.append('<span class="cell-quantity">' + str(quantity) + '</span>')

    if cbottom:
        markup.append('<div class="cell-bot">')
        markup += cbottom
        markup.append('</div>')

    if coloroverride:
        style = ' style="color: #{0};"'.format(coloroverride)

    quality = item.get("quality", "normal")

    markup.append(u'<div class="tooltip"><div class="prefix-{0} item-name"{1}>{2[mainname]}</div>'.format(quality, style, item))

    markup.append(generate_item_type_line(item))

    markup.append(generate_item_description(item))

    markup.append(generate_attribute_list(app, item, showlinks = False))

    markup.append(generate_item_paint_line(item))

    pricestr = generate_item_price_string(item, pricestats)

    if pricestr:
        markup.append('<div class="attr-neutral">{0}</div>'.format(pricestr))

    markup.append('</div></div>\n')

    return u''.join(markup)

def generate_class_icon_links(classes, ident, user = None, wiki_url = None):
    classlink = '#'
    markup = []
    classi = classes

    try: classi = classes.keys()
    except AttributeError: pass

    for ec in classi:
        cid, label = get_class_for_id(ec, ident)
        if user:
            classlink = generate_root_url("loadout/{0}/{1}".format(user["id64"], cid), ident)
        else:
            if wiki_url:
                classlink = wiki_url + str(label)
        markup.append('<a href="' + classlink + '">' + generate_class_sprite_img(ec, ident) + '</a> ')

    return u''.join(markup)

def generate_class_sprite_img(c, ident, styleextra = ""):
    ident = str(ident)
    ident = app_aliases.get(ident, ident)
    aliasmap = {
        "520": "440",
        "205790": "570"
        }
    sheetwidth = 512
    spritesize = 16

    try:
        ident = aliasmap.get(ident, ident)
        spriteindex, name = get_class_for_id(c, ident)

        if spriteindex >= 1000:
            spriteindex = 0

        spriteindex *= spritesize
        row, x = divmod(spriteindex, sheetwidth)
        row *= spritesize
        column = x

        style = "background: url('{0}') -{1}px -{2}px;".format(static_prefix + "class_icons/" + ident + ".png", column, row)
    except (ValueError, KeyError):
        style = ''
    except Exception as E:
        style = ''
        log.main.error("Failed class sprite img gen: " + repr(E))

    return '<img class="class-icon" src="{0}" style="{1}{2}" alt="{3}"/>'.format(static_prefix + "pixel.png", style, styleextra, c)
