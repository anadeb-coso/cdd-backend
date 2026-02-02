from django import template

register = template.Library()



@register.filter
def sub(value, arg):
    """Soustraction : {{ a|sub:b }}"""
    try:
        return int(value) - int(arg)
    except (ValueError, TypeError):
        return ''

@register.filter
def sub_float(value, arg):
    """Soustraction : {{ a|sub:b }}"""
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return ''