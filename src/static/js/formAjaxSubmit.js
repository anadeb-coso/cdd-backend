class FormAjaxSubmit {

    constructor(modal_size_class = "") {
        this.modal_size_class = modal_size_class;
    }

    submit_call(form, modal, url) {
        let self = this;
        $(form).submit(function (e) {
            e.preventDefault();
            $.ajax({
                type: "post",
                url: url,
                data: $(this).serialize(),
                success: function (xhr, ajaxOptions, thrownError) {
                    if ($(xhr).find('.is-invalid').length > 0 || $(xhr).find('.errorlist').length > 0) {
                        $(modal).html(xhr);
                        self.load_form(form, modal, url, true);
                    } else {
                        modal.modal('hide');
                        self.submitted_form(xhr);
                        showPopupMessage(xhr.msg);
                    }
                },
                error: function (xhr, ajaxOptions, thrownError) {
                    alert(error_server_message);
                }
            });
        });
    }

    submit_file_call(form, modal, url) {
        let self = this;
        $(form).submit(function (e) {
            e.preventDefault();
            $.ajax({
                type: "post",
                url: url,
                data: new FormData($(form).get(0)),
                cache: false,
                processData: false,
                contentType: false,
                success: function (xhr, ajaxOptions, thrownError) {
                    if ($(xhr).find('.is-invalid').length > 0 || $(xhr).find('.errorlist').length > 0) {
                        $(modal).html(xhr);
                        self.load_form(form, modal, url, true, true);
                    } else {
                        modal.modal('hide');
                        self.submitted_form(xhr);
                        showPopupMessage(xhr.msg);
                    }
                },
                error: function (xhr, ajaxOptions, thrownError) {
                    alert(error_server_message);
                }
            });
        });
    }

    submit_form(form, modal, url, file_form) {

        if (file_form) {
            this.submit_file_call(form, modal, url);
        } else {
            this.submit_call(form, modal, url);
        }
    }

// overwrite to call functions you need to run after loading the form
    loaded_form() {
    }

// overwrite to add extra functions you need to run after loading the form from when you open the modal
    first_loaded_form() {
    }

// overwrite to call functions you need to run after form submission
    submitted_form(xhr = null) {
    }

    load_form(form, modal, url, invalid_form = false, file_form = false) {
        let def = new $.Deferred();
        let self = this;
        if (invalid_form) {
            self.loaded_form();
            this.submit_form(form, modal, url, file_form);
        } else {
            modal.load(url, function (response, status, xhr) {
                if (status === "error") {
                    alert(error_server_message);
                } else {
                    modal.find('.modal-dialog').addClass(self.modal_size_class);
                    modal.modal('show');
                    self.loaded_form();
                    self.first_loaded_form();
                    def.resolve(true);
                    self.submit_form(form, modal, url, file_form);
                }
            });
        }
        return def;
    }
}
