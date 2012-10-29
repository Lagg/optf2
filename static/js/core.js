var invalidIconURL = jsConf.staticPrefix + "item_icons/Invalid_icon.png";

function makeToggleButton(label, id, callback, append) {
    var b = $('<input type="checkbox" id="' + id + '"/><label for="' + id + '">' + label + '</label>');
    if (append) { b.appendTo(append); }
    $("#" + id).button().click(callback);
}

$(document).ready(function(){
    $(document).on("mousedown", ".button, .ui-button", function() { return false; });
    $(".page-label").button();
    $("#feed-button").button({icons: {primary: "ui-icon-signal-diag"}});

    var cells = new ItemCells(), dialogs = new ItemDialog();

    cells.fitToContainer("#backpack");
    cells.bindTooltipHandlers();

    dialogs.bindOpenOnClick();
    dialogs.handleImgError("#content");

    var hashpage = URL.getHashStore("page");

    if (!hashpage) {
	hashpage = null;
    }

    if ($("#backpack").has(".backpack-page").length) {
	var pager = new BackpackPager("#backpack", hashpage);
	var paginationButton = $('<input type="checkbox" id="show-pages"/><label for="show-pages">Show Pages</label>');

	if (Cookie.get("pagination") || hashpage) {
	    paginationButton.attr("checked", "checked");
	    pager.modePaged();
	}

	paginationButton.appendTo(".item-tools");
	$("#show-pages").button().click(function() {
	    if (this.checked) {
		Cookie.set("pagination", true);
		pager.modePaged();
	    } else {
		Cookie.remove("pagination");
		pager.modeFull();
	    }

	});
    }

    /* Still somewhat experimental, aim to replace most
       of toolbar */
    var filterField = new Field("filterbar");
    var cellFilter = new CellFilter($(".item_cell"));

    filterField.attachTo(".item-tools");
    filterField.bindDefaultText("Search...");
    cellFilter.bindFilterToField(cellFilter.byRawAttribute, filterField);

    makeToggleButton("Hide untradable", "hide-untradable",
		     function () { unfade = !this.checked; cellFilter.fadeByAttrText("untradable", unfade); }, ".item-tools");

    makeToggleButton("Hide uncraftable", "hide-uncraftable",
		     function () { unfade = !this.checked; cellFilter.fadeByAttrText("uncraftable", unfade); }, ".item-tools");

    makeToggleButton("bbCode", "export-bbcode",
		     function() {
			 var textArea = $("#exportData");
			 if (textArea.length) {
			     textArea.text('');
			     textArea.remove();
			 } else {
			     var data = CellDataExport();
			     textArea = $('<textarea rows="30" cols="100" id="exportData"></textarea>');
			     textArea.text(data);
			     textArea.insertBefore(".backpack-page:first");
			     textArea.select();
			 }
		     }, ".item-tools");

    autosizeBoxes();

    var searchField = new Field("search-field");
    searchField.bindDefaultText("User, URL, or ID search...");

    /* May want to encapsulate stuff below later after testing. */
    var packdiv = $("#backpack");
    if (packdiv.length > 0) {
	$(".item-tools").width(packdiv.width());
	$(".item-tools").css("padding-right", packdiv.css("padding-right"));
	$('<div id="loadout-result" style="display: none;"></div>').insertBefore(packdiv);
    }

    $("#loadout-button").button({icons: {primary: "ui-icon-suitcase"}}).click(function(e) {
	var existingLoadout = $("#loadout");
	var theButton = $(this);

	e.preventDefault();

	theButton.toggleClass("clicked");

	if (existingLoadout.length == 0) {
	    var lastText = theButton.button("option", "label");
	    theButton.button("option", "label",  "Loading...");

	    $("#loadout-result").load(this.href + " #loadout",
				      function(data) {
					  $("#backpack").toggle();
					  $("#loadout-result").toggle();
					  theButton.button("option", "label", lastText);

					  autosizeBoxes();
				      });
	} else {
	    $("#backpack").toggle();
	    $("#loadout-result").toggle();
	}
    });
});

function autosizeBoxes() {
    $(".box.autosize").each(function() {
        var box = $(this);

        if(box.data("sized")) {
            return;
        }

        var innerlength = 0;
	var maxwidth = parseInt(box.css("max-width"));

        box.children().not(".titlebar").each(function() {
	    var nextwidth = $(this).outerWidth(true);

	    if ((innerlength + nextwidth) > maxwidth){
		return false;
	    } else {
		innerlength += nextwidth;
	    }
        });
        box.width(innerlength);

	box.data("sized", true);
    });
}

function BackpackPager (container, initialpage) {
    var pageSelector = ".backpack-page";
    var jSwitcher = null;
    var self = this;

    if (!container) {
	container = document;
    }

    this.activePages = $(container).find(pageSelector);
    this.currentPage = this.activePages.first();

    this.getPage = function(page) {
	var res = this.activePages.filter("#page-" + page);

	if (res.length <= 0) {
	    return null;
	} else {
	    return res;
	}
    };
    this.getCurrentPageId = function() {
	return this.currentPage.attr("id").slice(this.currentPage.attr("id").indexOf('-') + 1);
    };
    this.getCurrentPageIndex = function() {
	return this.activePages.index(this.currentPage);
    };

    this.switchPage = function() {
	var newpage = 0;
	var pages = self.activePages;
	var current = self.currentPage;
	var cIndex = self.getCurrentPageIndex();

	if (this.id == "item-page-forward") {
            newpage = cIndex + 1;
	} else if (this.id == "item-page-back") {
            newpage = cIndex - 1;
	}

	if (!pages[newpage]) {
	    return;
	}

	self.currentPage = $(pages[newpage]);
	$(pages).hide();
	self.currentPage.show();

	URL.setHashStore("page", self.getCurrentPageId());
	self.pageCounter.innerHTML = self.getCurrentPageId() + '/' + pages.length;

	self.setSwitcherButtonActivity();
    };

    var pagei = this.getPage(initialpage);
    if (pagei) {
	this.currentPage = pagei;
    } else {
	var hashstore = URL.getHashStore("page");
	pagei = this.getPage(hashstore);
	if (pagei) {
	    this.currentPage = pagei;
	}
    }

    this.pageSwitcher = document.createElement("div");
    this.pageSwitcher.id = "page-switcher";

    jSwitcher = $(this.pageSwitcher);

    this.pageBackButton = $('<button id="item-page-back">Previous</button>');
    this.pageBackButton.appendTo(this.pageSwitcher);
    this.pageBackButton.button({icons: {primary: "ui-icon-triangle-1-w"}}).click(this.switchPage);

    this.pageCounter = document.createElement("span");
    this.pageCounter.id = "page-counter";
    jSwitcher.append(this.pageCounter);

    this.pageForwardButton = $('<button id="item-page-forward">Next</button>');
    this.pageForwardButton.appendTo(this.pageSwitcher);
    this.pageForwardButton.button({icons: {secondary: "ui-icon-triangle-1-e"}}).click(this.switchPage);

    this.modeFull = function() {
	this.activePages.show();
	jSwitcher.detach();
	URL.removeHashStore("page");
    };

    this.modePaged = function() {
	var pages = this.activePages;
	var current = this.currentPage;

	jSwitcher.appendTo(container);

	URL.setHashStore("page", this.getCurrentPageId());
	this.pageCounter.innerHTML = this.getCurrentPageId() + '/' + pages.length;
	pages.hide();
	$(current).show();

	this.setSwitcherButtonActivity();
    };

    this.pageCount = function() {
	return this.activePages.length;
    }

    this.setSwitcherButtonActivity = function() {
	var cIndex = this.getCurrentPageIndex();
	pageForward = $("#item-page-forward");
	pageBack = $("#item-page-back");

	if (cIndex <= 0) {
            pageBack.button("disable");
	} else {
            pageBack.button("enable");
	}

	if (cIndex >= this.activePages.length - 1) {
            pageForward.button("disable");
	} else {
            pageForward.button("enable");
	}
    };
}

function ItemCells() {
    var cellSelector = ".item_cell";

    this.hoverHandler = function() {
	var cell = $(this);
	var win = $(window);
	var windowWidth = win.width();
	var windowHeight = win.height();
	var attribs = cell.find(".tooltip");
	var currentOffset = cell.offset();

	if (attribs.hasClass("inactive")) {
	    return;
	}

        attribs.show();
        currentOffset.top += cell.height() + 5;
        currentOffset.left -= (attribs.width() - cell.width()) / 2;

        /* Check if attribs go off the document */
        if (currentOffset.left < 0) { currentOffset.left = 0; }
        if((currentOffset.left + attribs.width()) > windowWidth) {
	    currentOffset.left = windowWidth - attribs.width();
        }

        attribs.offset(currentOffset);
        if (attribs.length > 0) {
	    var scrollh = $(document).scrollTop();
	    var offsety = attribs.offset().top;
	    var threshold = (scrollh + windowHeight);
	    var posbottom = (offsety + attribs.height());

	    if (posbottom > threshold) {
                attribs.offset({top: (cell.offset().top - attribs.height() - 5)});
	    }
        }
    };

    this.hoverOutHandler = function () { $(".tooltip").hide(); };

    this.bindTooltipHandlers = function() {
	$("#content").on("mouseenter", cellSelector, this.hoverHandler);
	$("#content").on("mouseleave", cellSelector, this.hoverOutHandler);
	$("#content").on("mouseenter", ".tooltip", this.hoverOutHandler);

	$(document).scroll(this.hoverOutHandler);
    }

    this.fitToContainer = function(container) {
	var jContainer = $(container);
	var containerCells = jContainer.find(".backpack-page .item_cell").not(".ungrouped > .item_cell");

	if (container && containerCells.length != 0) {
	    if(jContainer.length != 0) {
		jContainer.width(containerCells.outerWidth(true) * jsConf.cellsPerRow);
	    }
	}
    };
}

function rgb2hex(rgb) {
    var match = rgb.match(/^rgb\((\d+),\s*(\d+),\s*(\d+)\)$/);
    function hex(x) {
        return ("0" + parseInt(x).toString(16)).slice(-2);
    }

    var vals = [];
    for (var i = 1; i < match.length; i++) {
	var v = match[i];

	if (v > 180) {
	    v -= 100;
	}

	vals.push(hex(v));
    }

    var res = vals.join('');
    return "#" + res;
}

function CellDataExport() {
    var outputText = "";
    var SMNCColorMap = {
	"regular": "000000",
	"extra": "0040BF",
	"mega": "00BF00",
	"ultra": "BF00FF",
	"bacon": "FF8000"
    };

    $(".backpack-page").each(function() {
	var text = [];
	var page = $(this);
	var title = page.attr("id").split('-')[1];
	$(page.find(".item_cell").filter(":visible")).each(function() {
	    var cell = $(this);
	    var tt = cell.find(".tooltip");
	    var itemname = tt.find(".item-name");
	    var nametext = itemname.text();
	    var fullurl = cell.find(".item-link").prop("href");
	    var attrs = cell.find(".attribute-list");
	    var suffixText = "";
	    var quantity = /\(?(\d)\)?/.exec(cell.find(".equipped").html());

	    if (!nametext || attrs.text().toLowerCase().search("untradable") != -1) {
		return;
	    }

	    if (quantity) {
		quantity = '[b]x' + quantity[1] + '[/b] ';
	    } else {
		quantity = '';
	    }

	    nametext = nametext.replace(/(.+) (Regular|Extra|Mega|Ultra|Bacon)/, function(str, p1, p2, offset, s) {
		suffixText = " [b][color=#" + SMNCColorMap[p2.toLowerCase()] + "]" + p2 + "[/color][/b]";
		return p1;
	    });

	    text.push('[color=' + rgb2hex(itemname.css("color")) + '][b]' + nametext + '[/b][/color] ' + suffixText + ' ' + quantity + '- [url=' + fullurl + ']Link[/url]\n');
	});
	if (text.length > 0) {
	    text = text.sort().join('');
	    outputText += "[b][size=185]" + title + "[/size][/b]\n[list]\n" + text + "[/list]\n\n";
	}
    });

    return outputText;
}

function CellFilter(data) {
    var self = this;

    this.hasContainer = $(data).parent().hasClass("backpack-page");

    this.bindFilterToField = function(filter, field) {
	var f = field.baseField;
	var linkedFilter = URL.getHashStore("filter");

	if (f == undefined) {
	    f = field;
	}

	if (linkedFilter) {
	    f.value = linkedFilter;
	    filter(linkedFilter);
	}

	$(f).keyup(function() {
	    var input = this.value;

	    URL.setHashStore("filter", input);
	    filter(input);
	});
    };

    this.byRawAttribute = function(input) {
	var filter = input;
	var cells = $(data);

	if (self.hasContainer) { cells.parent().hide(); }
	cells.hide();

	if (!filter || filter.length == 0) {
	    if (self.hasContainer) { cells.parent().show(); }
	    cells.show();
	    return;
	}

	filter = filter.toLowerCase().replace(/\s+/g, " ");

	cells.each(function() {
	    var cell = $(this);
	    var attribs = cell.find(".tooltip");

	    if (cell.hasClass("cell-" + filter)) {
		if (self.hasContainer) { cell.parent().show(); }
		cell.show();
		return;
	    }

	    attribs.each(function() {
		if (this.innerHTML.toLowerCase().replace(/\s+/g, " ").search(filter) != -1) {
		    if (self.hasContainer) { cell.parent().show(); }
		    cell.show();
		    return false;
		}
	    });
	});
    };

    this.fadeByAttrText = function(text, unfade) {
	var cells = $(data);

	cells.each(function() {
	    var cell = $(this);
	    var tt = cell.find(".tooltip");
	    var attribs = cell.find(".attribute-list");

	    attribs.each(function() {
		if (this.innerHTML.toLowerCase().search(text.toLowerCase()) != -1) {
		    if (!unfade) {
			var fadeBox = $('<div class="fade-overlay ' + text + '">&nbsp;</div>');
			var b = parseInt(cell.css("border-width"));
			fadeBox.width(cell.width());
			fadeBox.height(cell.height());
			fadeBox.css("border-radius", cell.css("border-radius"));
			fadeBox.css("border-width", b);
			fadeBox.css("top", -b);
			fadeBox.css("left", -b);
			fadeBox.appendTo(cell);
			tt.addClass("inactive");
		    } else {
			cell.find(".fade-overlay." + text).remove();
			if (cell.find(".fade-overlay").length <= 0) {
			    cell.find(".tooltip.inactive").removeClass("inactive");
			}
		    }
		    return false;
		}
	    });
	});
    };
}

function Field(id) {
    var existingField = $("#" + id);

    if (existingField.length == 0) {
	this.baseField = document.createElement("input");
	this.baseField.type = "text";
	this.baseField.id = id;
    } else {
	this.baseField = existingField;
    }

    this.attachTo = function(element) {
	$(this.baseField).appendTo(element);
    };

    this.bindDefaultText = function(text) {
	var field = $(this.baseField);

	var focusIn = function() {
	    var value = field.val();

	    if (value == text) {
		field.val("");
	    }
	}
	var focusOut = function() {
	    var value = field.val();

	    if (value.length == 0) {
		field.val(text);
	    }
	}

	focusOut();
	field.focusin(focusIn);
	field.focusout(focusOut);
    };

    this.setText = function(text) {
	this.baseField.value = text;
    };

}

function ItemDialog() {
    var self = this;
    this.lastDialogSize = null;

    this.bindOpenOnClick = function() {
	$("#content").on("click", ".item_cell[id]", function(event) {
	    var cell = $(this);
            event.preventDefault();
            self.open(cell.attr("id"), cell.find("a.item-link").attr("href"));
	});
    };

    this.open = function(id, url) {
	var existingDialog = null;

	if (this.isLoadTickerRunning(id)) {
	    return;
	}

	this.toggleLoadTicker(id);

	existingDialog = $(".dedicated_item." + id);

	if (existingDialog.length > 0) {
	    this.toggleLoadTicker(id);
            existingDialog.dialog({open: this.resizeEvent});
	} else {
            $.get(url, this.openSuccessEvent, {}, "html");
	}
    };

    this.handleImgError = function (e) {
	$(e).find("img.item-image").one("error", function() {
	    this.src = invalidIconURL;
	});
	$(e).find('img.icon-particle').one("error", function() {
	    $(this).remove();
	});
    };

    this.openSuccessEvent = function (data, status, xhr) {
	var page = $(data);
	var title = page.filter("#header").find("h1");
	var content = page.filter("#content").find("#item_stats");
	var width = 850;
	var height = 670;
	var cellID = 's' + content.find(".item_id").text();

	content.addClass(cellID);

	self.toggleLoadTicker(cellID);

	if (self.lastDialogSize != null) {
            width = self.lastDialogSize.width;
            height = self.lastDialogSize.height;
	}

	title.css({"font-size": "1.6em", "margin": "0", "padding": "0"});

	var buttons = content.find(".item-attrs .link-list");
	var itemLink = $('#' + cellID + " .item-link").attr("href");
	var itemLinkButton = $('<a href="' + itemLink + '">Share</a>');
	buttons.append($("<li></li>").append(itemLinkButton));
	itemLinkButton.button({icons: {primary: "ui-icon-link"}});

	if ($(window).height() < height) {
            height = $(window).height();
	}
	if ($(window).width() < width) {
            width = $(window).width();
	}

	$(content).dialog({
            resize: self.resizeEvent,
            open: function(event, ui) {
		self.handleImgError(event.target);
		self.resizeEvent(event, ui);
            },
            title: title,
            width: width,
            height: height,
            minWidth: 250,
            minHeight: 200
	});
    };

    this.resizeScaled = function (elem, w, h) {
	var ew = elem.width();
	var eh = elem.height();
	var ratio = Math.min(w / ew, h / eh);

	elem.width(ratio * ew);
	elem.height(ratio * eh);
    };

    this.resizeEvent = function (event, ui) {
	var item = $(event.target);
	var image = item.find(".item-image, .icon-particle");
	var container = item.find(".item-zoom");
	var icons = item.find(".icon-custom-texture");


	if (ui.size == undefined) {
	    ui.size = new Object();
            ui.size.height = item.height();
            ui.size.width = item.width();
	} else {
            self.lastDialogSize = ui.size;
	}

	self.resizeScaled(image,
                          Math.min(ui.size.width - 200, 512),
                          Math.min(ui.size.height - 100, 512));

	icons.each(function() {
	    var icon = $(this);
	    var sizeKey = "initialSize";

	    if (!icon.data(sizeKey)) { icon.data(sizeKey, [icon.width(), icon.height()]); }

	    var size = icon.data(sizeKey);

	    self.resizeScaled(icon,
                              Math.min(container.width()/2.5, size[0]),
                              Math.min(container.height()/2.5, size[1]));
	});

	item.height(ui.size.height);
	item.width(image.width() + item.find(".item-attrs").width() + 50);
    };

    this.isLoadTickerRunning = function (id) {
	var ticker = $("#loading-" + id);

	return (ticker.length > 0);
    }

    this.toggleLoadTicker = function (id) {
	var tickerID = "loading-" + id;
	var tickerSelector = "#" + tickerID;
	var cellSelector = "#" + id;
	var ticker = $(document.createElement("img"));

	ticker.attr({
	    "src": jsConf.staticPrefix + "loading.gif",
	    "id": tickerID,
	    "class": "ticker",
	    "alt": "Loading..."
	});

	if (this.isLoadTickerRunning(id)) {
	    $(tickerSelector).remove();
	} else {
	    $(cellSelector).prepend(ticker);
	}

	return ticker;
    };
}

var Cookie = {
    remove: function(name) {
	document.cookie = name + "=0; expires=Thu Feb 17 2011 08:33:55 GMT-0700 (MST); path=/";

	return true;
    },

    get: function(name) {
	var cookies = document.cookie.split(';');

	for (var i = 0; i < cookies.length; i++) {
            var cookie = cookies[i];
	    var separator = cookie.indexOf('=');
            var cookieName = $.trim(cookie.substr(0, separator));
            var cookieValue = $.trim(cookie.substr(separator + 1));

            if (cookieName == name) {
		return cookieValue;
            }
	}

	return null;
    },

    set: function(name, val) {
	document.cookie = name + "=" + val + "; path=/";

	return true;
    }
}

var URL = {
    deserializeHashStore: function() {
	var values = {};
	var hashStores = location.hash.substr(1).split(';');

	for (var i = 0; i < hashStores.length; i++) {
	    var elem = hashStores[i];
	    var store = [elem, ''];
	    var sep = elem.indexOf('-');

	    if (!elem) {
		continue;
	    }

	    if (sep != -1) {
		store[0] = elem.slice(0, sep);
		store[1] = elem.slice(sep + 1);
	    }

	    values[decodeURI($.trim(store[0]))] = decodeURI($.trim(store[1]));
	}

	return values;
    },

    serializeHashStore: function(values) {
	var hashString = "";

	for (var key in values) {
	    var val = values[key];

	    hashString += encodeURI(key);

	    if (val) {
		hashString += '-' + encodeURI(values[key])
	    }

	    hashString += ';';
	}

	return hashString;
    },

    getHashStore: function(key) {
	var store = this.deserializeHashStore()[key];

	if (store == undefined) {
	    store = null;
	}

	return store;
    },

    setHashStore: function(key, val) {
	var hashes = this.deserializeHashStore();
	hashes[key] = val;

	location.hash = this.serializeHashStore(hashes);

	return true;
    },

    removeHashStore: function(key) {
	var hashes = this.deserializeHashStore();

	delete hashes[key];

	location.hash = this.serializeHashStore(hashes);

	return true;
    }
}
