var invalidIconURL = static_prefix + "item_icons/Invalid_icon.png";

$(document).ready(function(){
    var cells = new Cell("#backpack");

    cells.fitToContainer();
    cells.bindHoverAction();

    var hashpage = URL.getHashStore("page");

    if (!hashpage) {
	hashpage = null;
    }

    if ($("#backpack").has(".backpack-page").length) {
	var pager = new BackpackPager("#backpack", hashpage);
	var paginationButton = new Button("Show pages");

	paginationButton.attachTo(".item-tools");
	paginationButton.bindClickStateHandler(function(clicked) {
	    if (clicked) {
		if (!hashpage) {
		    Cookie.set("pagination", true);
		}
		pager.modePaged();
	    } else {
		if (!hashpage) {
		    Cookie.remove("pagination");
		}
		pager.modeFull();
	    }
	});

	if (Cookie.get("pagination") || hashpage) {
	    paginationButton.setClickState(true);
	}
    }

    var dialogs = new ItemDialog(".item-link");
    dialogs.bindOpenOnClick();

    /* Still somewhat experimental, aim to replace most
       of toolbar */
    var filterField = new Field("filterbar");
    var cellFilter = new CellFilter($(".item_cell"));

    filterField.attachTo(".item-tools");
    filterField.bindDefaultText("Search...");
    cellFilter.bindFilterToField(cellFilter.byRawAttribute, filterField);

    var untradableButton = new Button("Hide untradable");
    untradableButton.attachTo(".item-tools");
    untradableButton.bindClickStateHandler(function() {
	cellFilter.byUntradable();
    });

    var uncraftableButton = new Button("Hide uncraftable");
    uncraftableButton.attachTo(".item-tools");
    uncraftableButton.bindClickStateHandler(function() {cellFilter.byUncraftable();});

    autosizeBoxes();

    var searchField = new Field("search-field");
    searchField.bindDefaultText("User, URL, or ID search...");

    function autocomplete_magic(req, resp) {
	var finalcomp = new Array ();
	$.getJSON (virtual_root + "comp/" + req.term, function (data, status) {
	    for (var i = 0; i < data.length; i++) {
		itemdata = data[i];
		itemlabel = "";

		if (itemdata.avatar != undefined) { itemlabel += '<img width="16" height="16" src="' + itemdata.avatar + '"/> '; }

		itemlabel += itemdata.persona;
		if (itemdata.id_type == "id") {
		    itemlabel += " (" + itemdata.id + ')';
		}
		finalcomp.push({label: itemlabel, value: itemdata.id});
	    }

	    resp (finalcomp.slice (0, 20));
	});
    }

    searchField.baseField.autocomplete({
        minLength: 2,
        source: autocomplete_magic,
        open: function() { $(".ui-autocomplete").css("z-index", "100"); },
        select: function(e, ui) { this.value = ui.item.value; $("#search-form").submit(); }
    }).data("autocomplete")._renderItem = function(ul, item) {
	return $("<li></li>")
	    .data("item.autocomplete", item)
	    .append("<a>" + item.label + "</a>")
	    .appendTo(ul);
    };

    var sideBox = $(".side-box");
    if (sideBox.length > 0) {
	var sideBoxWidth = parseInt(sideBox.css("width"));
	sideBox.parent().css("padding-right", sideBoxWidth + 100 + "px");
    }

    /* May want to encapsulate stuff below later after testing. */
    var packdiv = $("#backpack");
    if (packdiv.length > 0) {
	$(".item-tools").width(packdiv.width());
	$(".item-tools").css("padding-right", packdiv.css("padding-right"));
	$('<div id="loadout-result" style="display: none;"></div>').insertBefore(packdiv);
    }

    $("#loadout-button").click(function(e) {
	var existingLoadout = $("#loadout");

	e.preventDefault();

	$(this).toggleClass("clicked");

	if (existingLoadout.length == 0) {
	    var lastText = this.innerHTML;
	    this.innerHTML = "Loading...";

	    $("#loadout-result").load(this.href + " #loadout",
				      function(data) {
					  var cells = new Cell(data);
					  var dialogs = new ItemDialog(".item-link");

					  $("#backpack").toggle();
					  $("#loadout-result").toggle();

					  $("#loadout-button").html(lastText);

					  dialogs.bindOpenOnClick();

					  cells.fitToContainer();
					  cells.bindHoverAction();

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

    this.pageBackButton = new Button("< Previous");
    this.pageBackButton.attachTo(this.pageSwitcher);

    this.pageCounter = document.createElement("span");
    this.pageCounter.id = "page-counter";
    jSwitcher.append(this.pageCounter);

    this.pageForwardButton = new Button("Next >");
    this.pageForwardButton.attachTo(this.pageSwitcher);

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
	this.pageCounter.textContent = this.getCurrentPageId() + '/' + pages.length;
	pages.hide();
	$(current).show();

	this.setSwitcherButtonActivity();
    };

    this.pageCount = function() {
	return this.activePages.length;
    }

    this.setSwitcherButtonActivity = function() {
	var bButton = $(this.pageBackButton.buttonElement);
	var fButton = $(this.pageForwardButton.buttonElement);

	var cIndex = this.getCurrentPageIndex();
	if (cIndex <= 0) {
            bButton.addClass("inactive");
	} else {
            bButton.removeClass("inactive");
	}

	if (cIndex >= this.activePages.length - 1) {
            fButton.addClass("inactive");
	} else {
            fButton.removeClass("inactive");
	}
    };

    this.switchPage = function(direction) {
	var newpage = 0;
	var pages = this.activePages;
	var current = this.currentPage;
	var cIndex = this.getCurrentPageIndex();

	if (direction == "forward") {
            newpage = cIndex + 1;
	} else if (direction == "back") {
            newpage = cIndex - 1;
	}

	if (!pages[newpage]) {
	    return;
	}

	this.currentPage = $(pages[newpage]);
	$(pages).hide();
	this.currentPage.show();

	URL.setHashStore("page", this.getCurrentPageId());
	this.pageCounter.innerHTML = this.getCurrentPageId() + '/' + pages.length;

	this.setSwitcherButtonActivity();
    };

    this.switchPageForward = function() {
	return self.switchPage("forward");
    };

    this.switchPageBack = function() {
	return self.switchPage("back");
    };

    this.pageForwardButton.bindOneOffHandler(this.switchPageForward);
    this.pageBackButton.bindOneOffHandler(this.switchPageBack);
}

function Button(defaultText) {
    this.buttonElement = document.createElement("div");
    this.buttonElement.className = "button";
    this.isClicked = false;
    var self = this;
    var stateHandler = null;
    var stateChangeFire = function() {
	if (self.isClicked) {
	    $(self.buttonElement).addClass("clicked");
	} else {
	    $(self.buttonElement).removeClass("clicked");
	}
	stateHandler.call(self.buttonElement, self.isClicked);
    };

    this.attachTo = function(element) {
	$(element).append(this.buttonElement);
    };

    this.bindClickStateHandler = function(handler) {
	stateHandler = handler;

	$(self.buttonElement).click(function() {
	    self.isClicked = !self.isClicked;
	    stateChangeFire();
	});
    };

    this.bindOneOffHandler = function(handler) {
	$(self.buttonElement).click(function() {
	    handler.call(this);
	});
    };

    this.setClickState = function(boolState) {
	this.isClicked = boolState;

	stateChangeFire();
    };

    this.setID = function(id) {
	this.buttonElement.id = id;
    };

    this.setText = function(text) {
	this.buttonElement.textContent = text;
    };

    if (defaultText) {
	this.setText(defaultText);
    }

    $(document).on("mousedown", ".button", function() { return false; });
}

function Cell(container) {
    var cellSelector = ".item_cell";
    var cells = [];
    var self = this;

    if ($(container).length == 0) {
	container = document;
    }

    cells = $(cellSelector);

    this.cellsPerRow = 10;

    this.bindHoverAction = function() {
	cells.hover(function() {
            var attribs = $(this).find(".tooltip");
            var currentOffset = $(this).offset();
	    var windowHeight = $(window).height();
	    var windowWidth = $(window).width();

            attribs.show();
            currentOffset.top += $(this).height() + 5;
            currentOffset.left -= (attribs.width() / 3.4);

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
                    attribs.offset({top: ($(this).offset().top - attribs.height() - 5)});
		}
            }
	}, function() {
            $(this).find(".tooltip").hide();
	});
	cells.find(".tooltip").hover(function() { $(this).hide(); });

	$(document).scroll(function() {
            cells.find(".tooltip").hide();
	});

	cells.find(".item-image").one("error", function() {
            this.src = invalidIconURL;
            $(this).addClass("invalid");
	});

	cells.find(".icon-particle").one("error", function() {
            $(this).remove();
	});
    };

    this.fitToContainer = function() {
	var jContainer = $(container);
	if (container && cells.length != 0) {
	    if(jContainer.length != 0) {
		/* Ignore "detached" cells that happen to be in the same container */
		jContainer.width(cells.not(".ungrouped > .item_cell").outerWidth(true) * this.cellsPerRow);
	    }
	}
    };
}

function CellFilter(data) {
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

	cells.hide();

	if (!filter || filter.length == 0) {
	    cells.show();
	    return;
	}

	filter = filter.toLowerCase();

	cells.each(function() {
	    var cell = $(this);
	    var attribs = cell.find(".tooltip");

	    if (cell.hasClass("cell-" + filter)) {
		cell.show();
		return;
	    }

	    attribs.each(function() {
		if (this.textContent.toLowerCase().search(filter) != -1) {
		    cell.show();
		    return false;
		}
	    });
	});
    };

    this.fadeByAttributeListContent = function(input) {
	var cells = $(data);

	cells.each(function() {
	    var cell = $(this);
	    var attribs = cell.find(".attribute-list");

	    attribs.each(function() {
		if (this.textContent.toLowerCase().search(input.toLowerCase()) != -1) { cell.toggleClass("faded"); }
	    });
	});
    };

    this.byUntradable = function(input) { return this.fadeByAttributeListContent("untradable"); };
    this.byUncraftable = function(input) { return this.fadeByAttributeListContent("uncraftable"); };
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

function ItemDialog(baseLink) {
    var self = this;
    this.itemURLMap = new Object();
    this.lastDialogSize = null;

    if (!baseLink) {
	throw new Error("Need a valid item link anchor selector");
    }

    $(baseLink).each(function() {
        var id = String($(this).parent().attr("id").slice(1));
        self.itemURLMap[id] = $(this).attr("href");
    });

    this.bindOpenOnClick = function() {
	$(baseLink).click(function(event) {
            event.preventDefault();
            self.open($(this).parent().attr("id").slice(1));
	});
    };

    this.open = function(id) {
	var url = this.itemURLMap[id];
	var existingDialog = null;

	if (this.isLoadTickerRunning(id)) {
	    return;
	}

	this.toggleLoadTicker(id);

	$(".dedicated_item").find("#item_id").each(function() {
	    if (this.textContent == id) {
		existingDialog = $(this).parentsUntil(".dedicated_item").parent().first();
		return false;
	    }
	});

	if (existingDialog) {
	    this.toggleLoadTicker(id);
            $(existingDialog).dialog({open: this.resizeEvent});
	} else {
            $.get(url, this.openSuccessEvent, {}, "html");
	}
    };

    this.openSuccessEvent = function (data, status, xhr) {
	var page = $(data);
	var title = page.filter("#header").find("h1");
	var content = page.filter("#content").find("#item_stats");
	var width = 850;
	var height = 670;
	var itemID = content.find("#item_id").text();

	self.toggleLoadTicker(itemID);

	if (self.lastDialogSize != null) {
            width = self.lastDialogSize.width;
            height = self.lastDialogSize.height;
	}

	title.css({"font-size": "1.6em", "margin": "0", "padding": "0"});

	var buttons = content.find(".item-attrs .button-list");
	buttons.append("<li><a class=\"button\" href=\"" + self.itemURLMap[itemID] + "\">Link to this item</a></li>");

	if ($(window).height() < height) {
            height = $(window).height();
	}
	if ($(window).width() < width) {
            width = $(window).width();
	}

	$(content).dialog({
            resize: self.resizeEvent,
            open: function(event, ui) {
		var cellImage = $("#s" + itemID + " .item-image");
		if (cellImage.hasClass("invalid")) {
		    $(event.target).find(".item-image").attr("src", invalidIconURL);
		}
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
	var image = item.find(".item-image");
	var container = item.find(".item-zoom");
	var icons = item.find(".icon-particle, .icon-custom-texture");


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
	var cellID = "s" + id;
	var cellSelector = "#" + cellID;
	var ticker = $(document.createElement("img"));

	ticker.attr({
	    "src": static_prefix + "loading.gif",
	    "id": tickerID,
	    "alt": "Loading..."
	});

	ticker.css({
	    "z-index": 5,
	    "position": "absolute",
	    "top": "37.5px",
	    "left": "37.5px"
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

	    values[decodeURI(store[0].trim())] = decodeURI(store[1].trim());
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
