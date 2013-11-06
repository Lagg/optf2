$(document).ready(function() {
    $("#rp-results").on("click", ".sr", function(e) {
	e.preventDefault();
	var resdiv = $(this).button();
	var url = resdiv.attr("href");

	if (resdiv.button("option", "icons").secondary == "ui-icon-loading") return;
	resdiv.button("option", "icons", {secondary: "ui-icon-loading"});
	$.get(url,
	      function(data) {
		  var boxes = $(data).filter("#content").children(".box");
		  $("#rp-results").fadeOut("fast");
		  $("#game-summaries").fadeIn("slow");
		  boxes.width(350);
		  boxes.css("margin", "1em");
		  boxes.css("float", "left");
		  $(".sr-slot").empty().append(resdiv.button("option", "icons", {secondary: "ui-icon-link"}));
		  resdiv.removeClass("ui-state-hover ui-state-focus");
		  boxes.appendTo("#game-summaries");
	      })
	.error(function() {
	    resdiv.button("option", {icons: {secondary: null }, disabled: true});
	    resdiv.css("border", "1px solid red");
	});
    });
    $("#rp-submit").button({icons: {primary: "ui-icon-search"}});
    var rpField = $("#rp-input"), rpFieldDefault = "Search Steam player profiles";
    rpField.addClass("inactive");
    rpField.val(rpFieldDefault);
    rpField.click(function() { if(rpField.hasClass("inactive")) { rpField.val(''); rpField.removeClass("inactive"); } });
    $("#rp-form").submit(function() {
	var output = $("#rp-results");
	var field = $("#rp-input");
	var val = field.val();

	if (!val || field.hasClass("inactive") || field.attr("disabled")) return false;

	var searchButton = $("#rp-submit");
	searchButton.hide();

	$('<b id="loading-txt">Searching...</b>').insertAfter(searchButton);
	field.attr("disabled", "disabled");

	$.getJSON(jsConf.vRoot + "api/profileSearch", {user: val}, function(data) {
	    output.empty();
	    $("#game-summaries").empty();
	    $.each(data, function() {
		var row = $('<a class="sr" href="/inv/' + this.id64 + '"><img class="avatar" src="' + this.avatarurl + '"/>' + this.persona + '</a>').button();
		if (this.exact)
		    row.css("color", "#6d89d5");
		row.appendTo(output);
	    });
	    if (data.length <= 0)
		output.prepend("No results found");
	    searchButton.show();
	    $("#loading-txt").remove();
	    field.removeAttr("disabled");
	    output.fadeIn("slow");
	});

	return false;
    });
});
