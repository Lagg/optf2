$(document).ready(function(){
    $(".item_link").removeAttr("href");
    var cells = $(".item_cell");
    cells.each(function() {
        $(this).click(function() {
            item_open(this.id.slice(1));
        });
    });
});

function item_image_resize(img, iw, ih, w, h) {
    var ratio = Math.min(w / iw, h / ih);

    img.width(ratio * iw);
    img.height(ratio * ih);
}

function item_resize(event, ui) {
    var item = $(event.target);
    var image = item.find("#item_image_large");

    item.height(ui.size.height);
    item.width(ui.size.width);
    item.find("#stat_vertrule").height(ui.size.height);

    item_image_resize(image, image.width(), image.height(),
                      Math.min(ui.size.width - 200, 512),
                      Math.min(ui.size.height - 100, 512));
}

function item_open_success(data, status, xhr) {
    var page = $(data);
    var dialog_title = page.filter("#header");
    var dialog_content = page.filter("#content").find("#item_stats");
    var dialog_width = 850;
    var dialog_height = 700;

    if ($(window).height() < dialog_height) {
        dialog_height = $(window).height();
    }
    if ($(window).width() < dialog_width) {
        dialog_width = $(window).width();
    }

    $("#loading_" + dialog_content.find("#item_id").html()).remove();

    $(dialog_content).dialog({
        resize: item_resize,
        title: dialog_title,
        width: dialog_width,
        height: dialog_height,
        modal: true
    });
}

function item_open(item_id) {
    var item_url = "/item/" + item_id;
    var loading_id = "loading_" + item_id;
    var cell_id = $("#s" + item_id);
    if (cell_id.find("#" + loading_id).length <= 0) {
        cell_id.prepend("<div id=\"" + loading_id + "\"><b>Loading...</b></div>");
    }
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
