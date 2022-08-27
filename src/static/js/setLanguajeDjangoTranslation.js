/*!
 * Submit the language change for Django Translation
 */

$(document).on("click", ".language", function () {
    document.language_form.language.value = $(this).data('language_code');
    document.language_form.submit()
});
