from datetime import datetime

from django import template

register = template.Library()


@register.filter
def get(dictionary, key):
    return dictionary.get(key, None)


@register.simple_tag
def date_order_format(date):
    data = date.split('-') if date else []
    return f'{data[2]}{data[1]}{data[0]}' if len(data) > 2 else ''


@register.simple_tag
def get_date(date_time):
    data = date_time.split('T') if date_time else ''
    if data:
        data = data[0].split('-')
        data = f'{data[2]}-{data[1]}-{data[0]}' if len(data) > 2 else ''
    return data


@register.filter(expects_localtime=True)
def string_to_date(date_time, date_format="%Y-%m-%dT%H:%M:%S.%fZ"):
    if date_time:
        return datetime.strptime(date_time, date_format)


@register.simple_tag
def get_days_until_today(date_time):
    date = datetime.strptime(date_time, '%Y-%m-%dT%H:%M:%S.%fZ')
    delta = datetime.now() - date
    return delta.days


@register.simple_tag
def get_days_until_date(date_time):
    date = datetime.strptime(date_time, '%Y-%m-%dT%H:%M:%S.%fZ')
    delta = date - datetime.now()
    return delta.days


@register.simple_tag
def get_percentage_style(percentage):
    style = 'danger'
    percentage = int(percentage)
    if percentage > 19:
        style = 'yellow'
    if percentage > 49:
        style = 'primary'
    return style


@register.filter
def next_in_circular_list(items, i):
    if i >= len(items):
        i %= len(items)
    return items[i]


@register.simple_tag
def get_initials(string):
    return ''.join((w[0] for w in string.split(' ') if w)).upper()


@register.simple_tag
def get_hour(date_time):
    data = date_time.split('T') if date_time else ''
    if data:
        data = data[1].split('.')[0]
    return data


@register.filter(name="structureTheFields")
def structure_the_fields(task):
    fields_values = {}
    if task.get("form_response"):
        for fields in task.get("form_response"):
            for field, value in fields.items():
                if type(value) in (dict, list):
                    if type(value) == list:
                        for l_field in value:
                            for field1, value1 in l_field.items():
                                if type(value1) in (dict, list):
                                    if type(value1) == list:
                                        for l_field in value1:
                                            for field2, value2 in l_field.items():
                                                fields_values[field2] = value2
                                    else:
                                        for field3, value3 in value1.items():
                                            if type(value3) == list:
                                                for l_field in value3:
                                                    for field4, value4 in l_field.items():
                                                        fields_values[field4] = value4
                                            else:
                                                fields_values[field3] = value3
                                else:
                                    fields_values[field1] = value1

                    else:
                        for field5, value5 in value.items():
                            if type(value5) in (dict, list):
                                if type(value5) == list:
                                    for l_field in value5:
                                        for field6, value6 in l_field.items():
                                            fields_values[field6] = value6
                                else:
                                    for field7, value7 in value5.items():
                                        fields_values[field7] = value7
                            else:
                                fields_values[field5] = value5
                else:
                    fields_values[field] = value
                    
    return fields_values
