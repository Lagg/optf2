import __builtin__
import json
import operator
import random

import web

from optf2 import markup
from optf2 import config
from optf2 import models
from optf2.api_views import profile_search

valid_modes = map(operator.itemgetter(0), config.ini.items("modes"))


class filtering:
    """ item list filtering, note that these are their own
    sets of filters which do different things and take different
    operands, unlike the sorting methods. Hence no automation, just
    a similar API """

    def __init__(self, items):
        self._items = items

    def byCapability(self, capability):
        self._items = [item for item in self._items if item and capability in item.get("caps", [])]
        return self._items

    def byClass(self, cls):
        # TODO: Figure out happy medium for showing items that are all-class
        self._items = [item for item in self._items if item and cls in item.get("equipable", [])]
        return self._items

    def byQuality(self, quality):
        self._items = [item for item in self._items if item and str(item.get("quality")) == str(quality)]
        return self._items

class sorting:
    """ Item list sorting """

    def byClass(self, v):
        return sorted(v.get("equipable", []))

    def byID(self, v):
        return v.get("id", v.get("sid"))

    def byLevel(self, v):
        return v.get("level", 0)

    def byName(self, v):
        if v.get("cname"):
            return v.get("mainname")
        else:
            return v.get("basename")

    bySchemaID = operator.itemgetter("sid")

    def bySlot(self, v):
        return v.get("slot", sorted(v.get("equipped", {}).values()))

    # Special, marks reverse ID sort
    byTime = lambda self, v: None

    def get_sort_methods(self):
        """ Returns a list of defined sort key methods """

        sorters = []
        prefix = "by"

        for m in dir(self):
            if m.startswith(prefix):
                sorters.append(m[len(prefix):])

        return sorters

    def sort(self, by, **kwargs):
        """ by takes a string that is
        the suffix of an implemented sort key method """

        if not by: return self._items

        # TODO: Sequential IDs aren't in at least 1 3rd party game
        try:
            sortkey = by

            if not callable(sortkey):
                sortkey = getattr(self, "by" + str(by))
        except AttributeError:
            pass
        else:
            if sortkey == self.byTime:
                return self.sort(self.byID, reverse = True)
            else:
                self._items.sort(key = sortkey, **kwargs)

        return self._items

    def __init__(self, items):
        self._items = items

class item_page(object):
    """ Class for building pages of items suitable for display """

    # Russia, for the sake of OPTF2. Give real symbol.
    currencysymbols = {"USD": "$",
                       "RUB": "",
                       "GBP": unichr(0x00A3),
                       "EUR": unichr(0x20AC)}

    def __init__(self, items):
        self._items = items

    def build_page(self, pagesize=None, ignore_pos=False):
        """ Build a page map containing null elements as needed to represent
        empty cells. Obeys positioning info. Returns a touple containing the page dict
        and displaced items. The dict key is the page name and the value is the padded item list
        """

        imap = {}
        displaced = []

        if not pagesize:
            pagesize = 50

        if ignore_pos:
            return self.build_page_unpositioned(pagesize), displaced

        for item in self._items:
            if not item: continue

            itempos = item.get("pos")

            if not itempos:
                displaced.append(item)
                continue

            # Will use page names before
            # numbered if available
            pagename = item.get("cat")
            posrem = itempos % pagesize
            if posrem > 0: posrem += pagesize - posrem
            pageno = (itempos + posrem) / pagesize
            page = pageno
            roundedsize = pageno * pagesize
            realsize = pagesize

            if pagename:
                page = pagename
                realsize = roundedsize
            else:
                itempos -= roundedsize + 1

            imap.setdefault(page, [])
            pagelen = len(imap[page])
            if realsize > pagelen:
                imap[page] += [None] * ((realsize - pagelen) + 1)

            if imap[page][itempos] == None:
                imap[page][itempos] = item
            else:
                overlapped = imap[page][itempos]
                if overlapped.get("id") > item.get("id"):
                    imap[page][itempos] = item
                    displaced.append(overlapped)
                else:
                    displaced.append(item)

        mkeys = sorted(imap.keys())
        mapkeys = set(mkeys)
        for key in mapkeys: del imap[key][0]

        return imap, displaced

    def build_page_unpositioned(self, pagesize=None):
        """ Do the same thing build page does but without using positioning info and using
        item order as listed. Returns only item map without displaced items since
        there aren't any.
        """

        if not pagesize:
            pagesize = 50

        fitems = filter(None, self._items)
        ilen = len(fitems)
        pagecount = (ilen + (pagesize - (ilen % pagesize))) / pagesize
        imap = {}

        for page in xrange(1, pagecount + 1):
            offset = page * pagesize
            itemslice = fitems[offset - pagesize:offset]
            imap[page] = itemslice + ([None] * (pagesize - len(itemslice)))

        return imap

    def build_price_summary(self, assetcatalog):
        """ Builds a summary dict containing a rought estimate of prices for the items on the
        page according to the given asset catalog.
        """

        try:
            assets = assetcatalog.price_map
        except:
            assets = {}

        stats = {"assets": assets, "sym": self.currencysymbols, "worth": {}, "most-expensive": [], "avg": {}}

        if not assets:
            return stats

        worth = stats["worth"]
        costs = []
        count = 0

        for item in self._items:
            if not item: continue
            # TODO? Checking origin string directly may cause problems for non-english origins
            origin = item.get("origin", '')
            if "id" in item and origin.lower() != "purchased":
                continue # Not explicit purchase
            try:
                asset = assets[str(item.get("sid"))]
                count += 1
            except KeyError: continue
            costs.append((item, asset))
            for k, v in asset.iteritems():
                self.currencysymbols.setdefault(k, '')
                if k not in worth:
                    worth[k] = v
                else:
                    worth[k] += v

        stats["most-expensive"] = [item for item in sorted(costs, reverse = True, key = operator.itemgetter(1))[:10]]

        if count != 0:
            for k, v in worth.iteritems():
                stats["avg"][k] = round((v / count), 2)

        return stats

    @property
    def summary(self):
        """ A dict containing a summary of the items in the page """

        stats = {"total": 0}
        merged = {
            "weapons": ["primary", "secondary", "melee", "weapon"],
            "hats": ["hat", "head"],
            "cosmetic": ["misc"],
            "pda": ["pda", "pda2"],
            "other": ["none"]
            }

        for item in self._items:
            if not item:
                continue

            slot = item.get("slot", "none")

            stats["total"] += 1

            ismerged = False

            for label, slots in merged.iteritems():
                if slot.lower() in slots:
                    stats.setdefault(label, 0)
                    stats[label] += 1
                    ismerged = True

            if not ismerged:
                stats.setdefault(slot, 0)
                stats[slot] += 1

        # Redundancy check
        othercount = stats.get("other")
        if othercount and othercount == stats["total"]:
            del stats["other"]

        return stats

def build_dropdowns(items):
    """ Builds a list of dropdown operands based on the items given. """
    classes = set()
    qualities = set()
    caps = set()

    for item in items:
        if not item:
            continue

        classes |= set(item.get("equipable", []))
        caps |= set(item.get("caps", []))
        qualities.add(item.get("quality"))

    return {"capabilities": sorted(caps), "equipable_classes": sorted(classes), "qualities": sorted(qualities)}

def template_setup(directory, base=None):
    wikimap = {}
    for mode, wiki in config.ini.items("wiki"):
        wikimap[mode] = map(str.strip, wiki.split(':', 1))

    # Using this from web.template, don't want to import entire __builtin__
    # module (i.e. eval) so this will do
    TEMPLATE_BUILTIN_NAMES = [
        "dict", "enumerate", "float", "int", "bool", "list", "long", "reversed",
        "set", "slice", "tuple", "xrange",
        "abs", "all", "any", "callable", "chr", "cmp", "divmod", "filter", "hex",
        "id", "isinstance", "iter", "len", "max", "min", "oct", "ord", "pow", "range",
        "True", "False",
        "None",
        "len", "map", "str",
        "__import__", # some c-libraries like datetime requires __import__ to present in the namespace
    ]

    TEMPLATE_BUILTINS = dict([(name, getattr(__builtin__, name)) for name in TEMPLATE_BUILTIN_NAMES if name in __builtin__.__dict__])

    # These should stay explicit
    globals = {"virtual_root": config.ini.get("resources", "virtual-root"),
               "static_prefix": config.ini.get("resources", "static-prefix"),
               "encode_url": web.urlquote,
               "instance": web.ctx,
               "project_name": config.ini.get("misc", "project-name"),
               "wiki_map": wikimap,
               "qurl": web.http.changequery,
               "markup": markup,
               "game_modes": markup.odict(config.ini.items("modes")),
               "pagesizes": markup.get_page_sizes(),
               "json_dump": json.dumps,
               "json_load": json.loads,
               "f2p_check": config.ini.getlist("misc", "f2p-check-modes")
               }

    return web.template.render(directory, base=base, globals=globals, builtins=TEMPLATE_BUILTINS)

template = template_setup(config.ini.get("resources", "template-dir"), "base")

class index:
    def GET(self, app = None):
        usestale = True

        # Until dedicated main homepage is done
        if not app:
            app = random.choice(valid_modes)

        app = models.app_aliases.get(app, app)
        query = web.input()
        user = query.get("user")

        # TODO: Won't be much use in the big restructuring, for now try to extract app from path
        appfrom = query.get("from", '')[len(markup.virtual_root):].strip('/').split('/')[0]
        if appfrom not in valid_modes:
            appfrom = valid_modes[0]

        profile = profile_search(user)
        if profile:
            raise web.seeother(markup.generate_root_url("user/" + str(profile[0]["id64"]), appfrom))

        ckey = "scrender"
        showcase = models.cache.get(ckey)
        showcase_cell = None
        try:
            if not showcase:
                sitems = models.schema(scope = app).processed_items.values()
                if len(sitems) > 0:
                    showcase = random.choice(sitems)
                    showcase["app"] = app
                    # May want to add an option for showcase expiration to config later
                    models.cache.set(ckey, showcase, time=60)

            app = showcase.get("app", app)
            showcase_cell = markup.generate_item_cell(app, showcase, user=showcase.get("user"))
        except Exception as E:
            pass

        markup.init_theme(app)
        web.ctx.notopsearch = True

        # Last packs
        packs = models.recent_inventories(scope = app)

        return template.index(app, (packs or []), showcase_cell)

class about:
    def GET(self):
        return template.about()
