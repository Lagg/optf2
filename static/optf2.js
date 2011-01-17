$(document).ready(function(){
    $(".item_link").removeAttr("href");
    var cells = $(".item_cell");

    cells.hover(function() {
        var attribs = $(this).find(".item_attribs");
        attribs.show();
        if (attribs.length) {
            var scrollh = $(document).scrollTop();
            /* When a browser supports something simple yet non-standard like
               window.innerHeight, IE has to be ULTRA non-standard.
            */
            var windowh = document.documentElement.clientHeight;
            var offsety = attribs.offset().top;
            var threshold = (scrollh + windowh);
            var posbottom = (offsety + attribs.height());
            if (this.deftop == undefined) {
                this.deftop = attribs.css("top");
            }

            if (posbottom > threshold) {
                attribs.css("top", (-attribs.height() - 17) + "px");
            } else {
                attribs.css("top", this.deftop);
            }
        }
    }, function() {
        var attribs = $(this).find(".item_attribs");
        attribs.css("top", this.deftop);
        attribs.hide();
    });

    $(document).scroll(function() {
        $(".item_attribs").hide();
    });

    cells.click(function() {
        item_open(this.id.slice(1));
    });
});

function item_image_resize(img, iw, ih, w, h) {
    var ratio = Math.min(w / iw, h / ih);

    img.width(ratio * iw);
    img.height(ratio * ih);
}

function item_resize_event(event, ui) {
    var item = $(event.target);
    var image = item.find("#item_image_large");

    if (ui.size == undefined) {
        ui.size = {"height":  item.height(),
                   "width": item.width()};
    }

    item_image_resize(image, image.width(), image.height(),
                      Math.min(ui.size.width - 200, 512),
                      Math.min(ui.size.height - 100, 512));

    item.height(ui.size.height);
    item.width(image.width() + item.find("#item_attrs").width() + 50);
    item.find("#stat_vertrule").height(ui.size.height);
}

function item_open_success(data, status, xhr) {
    var page = $(data);
    var dialog_title = page.filter("#header").find("h1");
    var dialog_content = page.filter("#content").find("#item_stats");
    var dialog_width = 850;
    var dialog_height = 670;
    var item_id = dialog_content.find("#item_id").html();

    dialog_content.find("#item_attrs").append("<br/><br/><a href=\"" + virtual_root + "item/" + item_id + "\">Link to this item</a>");
    dialog_title.css({"font-size": "1.6em", "margin": "0", "padding": "0"});

    if ($(window).height() < dialog_height) {
        dialog_height = $(window).height();
    }
    if ($(window).width() < dialog_width) {
        dialog_width = $(window).width();
    }

    $("#loading_" + item_id).remove();

    $(dialog_content).dialog({
        resize: item_resize_event,
        open: item_resize_event,
        title: dialog_title,
        width: dialog_width,
        height: dialog_height,
        minWidth: 250,
        minHeight: 200,
        modal: true
    });
}

function item_open(item_id) {
    var item_url = virtual_root + "item/" + item_id;
    var loading_id = "loading_" + item_id;
    var cell_id = $("#s" + item_id);
    if (cell_id.find("#" + loading_id).length > 0) {
        return;
    }
    cell_id.prepend("<div id=\"" + loading_id + "\"><b>Loading...</b></div>");
    var oldcontent = $("body").find(".dedicated_item");
    var reallyoldcontent = null;
    for (var i = 0; i < oldcontent.length; i++) {
        var id = $(oldcontent[i]).find("#item_id").html();
        if (id == item_id) {
            reallyoldcontent = oldcontent[i];
            break;
        }
    }

    if (reallyoldcontent) {
        $(reallyoldcontent).dialog({open: function(e, u) { $("#" + loading_id).remove(); }});
    } else {
        $.get(item_url, item_open_success, {}, "html");
    }
}

function autocomplete_magic(req, resp) {
  var finalcomp = new Array ();
  $.getJSON (virtual_root + "comp/" + req.term, function (data, status) {
      for (var i = 0; i < data.length; i++) {
          itemdata = data[i]
          itemlabel = itemdata["persona"];
          if (itemdata["id_type"] == "id") {
              itemlabel += " (" + itemdata["id"] + ')';
          }
          finalcomp.push({label: itemlabel, value: itemdata["id"]});
      }

      resp (finalcomp.slice (0, 20));
  });
}

function autocomplete_attach(uid) {
    $("#user").autocomplete({
        minLength: 2,
        source: autocomplete_magic
    });
}
