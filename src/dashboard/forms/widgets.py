from django import forms


class RadioSelect(forms.RadioSelect):
    input_type = 'radio'
    option_template_name = 'widgets/radio_option.html'
