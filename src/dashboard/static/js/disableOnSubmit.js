<!-- Disable button on submit -->

function disableOnSubmit(selector) {
    selector.find(":submit").attr('disabled', 'disabled');
    selector.find(".disabled-on-submit").addClass('disabled');
    selector.find(".submit-spin").show();
}

$(".submit-spin").hide();

$("form").submit(function () {
    disableOnSubmit($(this))
});
$(".disabled-on-submit").click(function () {
    disableOnSubmit($("form"));
});
