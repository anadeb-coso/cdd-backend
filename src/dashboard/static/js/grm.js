<!-- Constants -->
const error_server_message = "An error has occurred, please check your network connection and try again. ";

<!-- Django messages -->
/**
 * Show alerts and hide success alerts after 4 seconds
 */

$(".alert-div-content").fadeIn();
window.setTimeout(function () {
    $(".alert-success").fadeOut();
}, 4000);

// alerts displayed in modal
$(".messageModal").modal("show");
window.setTimeout(function () {
    $(".modal-success").modal("hide");
}, 4000);

// It is used to show the alerts from an ajax call
function showPopupMessage(content) {
    if (content) {
        if (content.includes("alert-danger")) {
            window.scrollTo({top: 0, behavior: 'smooth'});
        }
        let messages = $('#popup-messages-content');
        if (messages.length && content) {
            messages.html(content);
        }
        $(".alert-div-content").fadeIn();
        window.setTimeout(function () {
            $(".alert-success").fadeOut();
        }, 4000);

        $(".messageModal").modal("show");
        window.setTimeout(function () {
            $(".modal-success").modal("hide");
        }, 4000);
    }
}

$('.form-check').addClass("icheck-primary");

function delay(callback, ms) {
    let timer = 0;
    return function () {
        let context = this, args = arguments;
        clearTimeout(timer);
        timer = setTimeout(function () {
            callback.apply(context, args);
        }, ms || 0);
    };
}
