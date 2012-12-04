$(document).ready(function() {
    $("#rp-results").on("click", ".sr", function(e) {
	e.preventDefault();
	var resdiv = $(this);
	if (resdiv.find(".purl .loading").length > 0) return;
	resdiv.find(".purl").append(' <img class="loading" src="' + jsConf.staticPrefix + 'loading.gif"/>');
	$.get(resdiv.find("a").attr("href"),
	      function(data) {
		  resdiv.find(".loading").remove();
		  var boxes = $(data).filter("#content").children(".box");
		  if (boxes.length <= 0) {
		      resdiv.button("disable");
		      resdiv.css("border", "1px solid red");
		      return;
		  }
		  $("#rp-results").fadeOut("fast");
		  $("#game-summaries").fadeIn("slow");
		  boxes.width(350)
		  boxes.css("margin", "1em");
		  boxes.css("float", "left");
		  boxes.appendTo("#game-summaries");
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
		var row = $('<div class="sr"><a class="purl" href="/inv/' + this.id64 + '"><img class="avatar" src="' + this.avatarurl + '"/>' + this.persona + '</a></div>').button();
		if (this.exact)
		    row.find("a").css("color", "#6d89d5");
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
