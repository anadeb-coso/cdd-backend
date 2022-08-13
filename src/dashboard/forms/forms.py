from django import forms
from django.conf import settings
from django.template.defaultfilters import filesizeformat
from django.utils.translation import gettext_lazy as _


class FileForm(forms.Form):
    file = forms.FileField(label='', help_text=_('Allowed file size less than or equal to 2 MB'))

    default_error_messages = {
        'file_size': _('Select a file size less than or equal to %(max_size)s. The selected file size is %(size)s.')}

    def clean_file(self):
        max_upload_size = settings.MAX_UPLOAD_SIZE
        value = self.cleaned_data.get('file')
        if value and value.size > max_upload_size:
            raise forms.ValidationError(
                self.default_error_messages['file_size'] % {
                    'max_size': filesizeformat(max_upload_size),
                    'size': filesizeformat(value.size)})
        return value
