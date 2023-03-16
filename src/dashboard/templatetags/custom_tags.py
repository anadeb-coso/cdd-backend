from datetime import datetime
from django import template
from django.utils.translation import gettext_lazy

from dashboard.utils import structure_the_words as utils_structure_the_words

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



@register.filter(name="structureTheFieldsLabels")
def structure_the_fields_labels(task):
    fields_values = []
    if task.get("form_response"):
        i = 0
        form = task.get("form")
        for fields in task.get("form_response"):
            fields_options = form[i].get('options').get('fields')
            dict_values = {}
            for field, value in fields.items():
                label = fields_options.get(field).get('label')
                if type(value) in (dict, list):
                    if type(value) == list:
                        _list1 = []
                        for l_field in value:
                            item1 = {}
                            for field1, value1 in l_field.items():
                                if type(value1) in (dict, list):
                                    if type(value1) == list:
                                        _list2 = []
                                        for l_field in value1:
                                            item2 = {}
                                            for field2, value2 in l_field.items():
                                                item2[field2] = {'name': utils_structure_the_words(field2), 'value': value2}
                                            _list2.append(item2)
                                        item1[field1] = {'name': utils_structure_the_words(field1), 'value': _list2}
                                    else:
                                        dict1 = {}
                                        for field3, value3 in value1.items():
                                            if type(value3) == list:
                                                _list3 = []
                                                for l_field in value3:
                                                    item4 = {}
                                                    for field4, value4 in l_field.items():
                                                        item4[field4] = {'name': utils_structure_the_words(field4), 'value': value4}
                                                    _list3.append(item4)
                                                dict1[field3] = {'name': utils_structure_the_words(field3), 'value': _list3}
                                            else:
                                                dict1[field3] = {'name': utils_structure_the_words(field3), 'value': value3}
                                        item1[field1] = {'name': utils_structure_the_words(field1), 'value': dict1}
                                else:
                                    item1[field1] = {'name': utils_structure_the_words(field1), 'value': value1}
                            _list1.append(item1)
                        dict_values[field] = {'name': label if label else utils_structure_the_words(field), 'value': _list1}
                    else:
                        dict2 = {}
                        ii = 0
                        for field5, value5 in value.items():
                            fields1 = fields_options.get(field).get('fields')
                            try:
                                label1 = fields1[field5].get('label') if fields1[field5].get('label') else utils_structure_the_words(field5)
                            except Exception as ex:
                                label1 = utils_structure_the_words(field5)
                            if type(value5) in (dict, list):
                                if type(value5) == list:
                                    _list4 = []
                                    for l_field in value5:
                                        item5 = {}
                                        for field6, value6 in l_field.items():
                                            item5[field6] = {'name': utils_structure_the_words(field6), 'value': value6}
                                        _list4.append(item5)
                                    dict2[field5] = {'name': label1, 'value': _list4}
                                else:
                                    item6 = {}
                                    for field7, value7 in value5.items():
                                        try:
                                            label2 = fields1[field5].get('fields').get(field7).get('label') if fields1[field5].get('fields').get(field7).get('label') else utils_structure_the_words(field7)
                                        except Exception as ex:
                                            label2 = utils_structure_the_words(field7)

                                        if type(value7) in (dict, list):
                                            if type(value7) == list:
                                                _list5 = []
                                                for l_field in value7:
                                                    item7 = {}
                                                    for field8, value8 in l_field.items():
                                                        item7[field8] = {'name': utils_structure_the_words(field8), 'value': value8}
                                                    _list5.append(item7)
                                                dict2[field5] = {'name': label2, 'value': _list5}
                                            else:
                                                item8 = {}
                                                for field9, value9 in value7.items():
                                                    try:
                                                        label3 = fields1[field5].get('fields').get(field7).get('fields').get(field9).get('label') if fields1[field5].get('fields').get(field7).get('fields').get(field9).get('label') else utils_structure_the_words(field9)
                                                    except Exception as ex:
                                                        label3 = utils_structure_the_words(field9)
                                                    item6[field7] = {'name': label3, 'value': value9}
                                                dict2[field5] = {'name': label2, 'value': item6}
                                        else:
                                            dict2[field7] = {'name': label2, 'value': value7}


                                        # item6[field7] = {'name': label2, 'value': value7}
                                    dict2[field5] = {'name': label1, 'value': item6}
                            else:
                                dict2[field5] = {'name': label1, 'value': value5}
                            ii += 1
                        dict_values[field] = {'name': label if label else utils_structure_the_words(field), 'value': dict2}
                else:
                    dict_values[field] = {'name': label if label else utils_structure_the_words(field), 'value': value}
            fields_values.append(dict_values)
            i += 1
    # print(fields_values)
    return fields_values


@register.filter(name="checkType")
def check_type(elt, _type):
    return  type(elt).__name__ == _type

@register.filter(name="structureTheWords")
def structure_the_words(word):
    return utils_structure_the_words(word)

@register.filter(name="imgAWSS3Filter")
def img_aws_s3_filter(uri):
    return uri.split("?")[0]

@register.filter(name='has_group') 
def has_group(user, group_name):
    return user.groups.filter(name=group_name).exists() 

@register.filter(name='get_group_high') 
def get_group_high(user):
    """
    All Groups permissions
        - SuperAdmin        : 
        - CDD Specialist    : CDDSpecialist
        - Admin             : Admin
        - Evaluator         : Evaluator
        - Accountant        : Accountant
    """
    if user.is_superuser:
        return gettext_lazy("Principal Administrator").__str__()
    
    if user.groups.filter(name="Admin").exists():
        return gettext_lazy("Administrator").__str__()
    if user.groups.filter(name="CDDSpecialist").exists():
        return gettext_lazy("CDD Specialist").__str__()
    if user.groups.filter(name="Evaluator").exists():
        return gettext_lazy("Evaluator").__str__()
    if user.groups.filter(name="Accountant").exists():
        return gettext_lazy("Accountant").__str__()


    return gettext_lazy("User").__str__()