from datetime import datetime
from django import template
from django.utils.translation import gettext_lazy
from django.db.models import Sum
from django.contrib.auth.models import Group

from assignments.models import AssignAdministrativeLevelToFacilitator
from cdd.call_objects_from_other_db import mis_objects_call
from process_manager.models import AggregatedStatus
from cdd.functions import get_validation_code

from dashboard.utils import structure_the_words as utils_structure_the_words
from dashboard.functions import order_dict
from authentication.models import Facilitator
from planning.models import Activity as PlanActivity, ValidationGroupsProcess

register = template.Library()


@register.filter
def get(dictionary, key):
    return dictionary.get(key, None)

@register.simple_tag
def get_code_email(email):
    code = "-"
    if email:
        code = get_validation_code(email)
    return code

@register.simple_tag
def date_order_format(date):
    data = date.split('-') if date else []
    return f'{data[2]}{data[1]}{data[0]}' if len(data) > 2 else ''

@register.filter
def get_indexed_user(dictionary, key):
    return dictionary.get(key, 0)

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
    if not string or string in ('', ):
        return 'N'
    return ''.join((w[0] for w in string.split(' ') if w)).upper()


@register.simple_tag
def get_hour(date_time):
    data = date_time.split('T') if date_time else ''
    if data:
        data = data[1].split('.')[0]
    return data

@register.filter
def truncate_with_dots(value, length):
    if len(value) > length:
        return value[:length] + '...'
    return value


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
            try:
                fields_options = form[i].get('options').get('fields')
            except:
                fields_options = {}
            dict_values = {}
            for field, value in fields.items():
                try:
                    label = fields_options.get(field).get('label')
                except:
                    label = utils_structure_the_words(field)
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
                        value = order_dict(task.get('sql_id'), field, value)
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
                                                item6[field5] = {'name': label2, 'value': _list5}
                                            else:
                                                item8 = {}
                                                for field9, value9 in value7.items():
                                                    try:
                                                        label3 = fields1[field5].get('fields').get(field7).get('fields').get(field9).get('label') if fields1[field5].get('fields').get(field7).get('fields').get(field9).get('label') else utils_structure_the_words(field9)
                                                    except Exception as ex:
                                                        label3 = utils_structure_the_words(field9)
                                                    item8[field7] = {'name': label3, 'value': value9}
                                                item6[field5] = {'name': label2, 'value': item6}
                                        else:
                                            item6[field7] = {'name': label2, 'value': value7}


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

@register.filter(name="is_pdf")
def is_pdf(uri):
    uri = uri.split("?")[0]
    return uri.split(".")[-1] in ['pdf', 'docx']


@register.filter(name="not_local")
def not_local(uri):
    return uri.split(":")[0] != 'file'

@register.filter(name="replace")
def replace(v: str, s: str):
    v = str(v)
    if "r|" in s:
        if len(s.split('r|')) != 2:
            return v
        else:
            what, to = s.split('r|')
            return v.replace(what, to)
    else:
        _ = s.split(";")
        for elt in _:
            v = v.replace(elt, "")
    return v

    
@register.filter
def get_item(dictionary, key):
    try:
        return int(dictionary.get(key))
    except ValueError:
        return dictionary.get(key)

@register.filter(name='has_group') 
def has_group(user, group_name):
    return user.groups.filter(name=group_name).exists() 

@register.filter(name='has_perm') 
def has_perm(user, perm_name):
    return user.user_permissions.filter(name=perm_name).exists() 

@register.filter(name='has_per') 
def has_per(user):
    return user.user_permissions

@register.filter(name='get_group_high') 
def get_group_high(user):
    """
    All Groups permissions
        - SuperAdmin            : 
        - CDD Specialist        : CDDSpecialist
        - Admin                 : Admin
        - Evaluator             : Evaluator
        - Accountant            : Accountant
        - Regional Coordinator  : RegionalCoordinator
        - National Coordinator  : NationalCoordinator
        - General Manager  : GeneralManager
        - Director  : Director
        - Advisor  : Advisor
        - Minister  : Minister
    """
    if user:
        if user.is_superuser:
            return gettext_lazy("Principal Administrator").__str__()
        
        if user.groups.filter(name="Admin").exists():
            return gettext_lazy("Administrator").__str__()
        
        if user.groups.filter(name="Minister").exists():
            return gettext_lazy("Minister").__str__()
        if user.groups.filter(name="Advisor").exists():
            return gettext_lazy("Advisor").__str__()
        if user.groups.filter(name="GeneralManager").exists():
            return gettext_lazy("General Manager").__str__()
        if user.groups.filter(name="NationalCoordinator").exists():
            return gettext_lazy("National Coordinator").__str__()
        if user.groups.filter(name="RegionalCoordinator").exists():
            return gettext_lazy("Regional Coordinator").__str__()
        if user.groups.filter(name="Director").exists():
            return gettext_lazy("Director").__str__()
        
        if user.groups.filter(name="Evaluator").exists():
            return gettext_lazy("Evaluator").__str__()
        if user.groups.filter(name="Financial").exists():
            return gettext_lazy("Financial ").__str__()
        if user.groups.filter(name="ProcurementSpecialist").exists():
            return gettext_lazy("Procurement Specialist").__str__()
        if user.groups.filter(name="KnowledgeManager").exists():
            return gettext_lazy("Knowledge manager").__str__()
        if user.groups.filter(name="CDDSpecialist").exists():
            return gettext_lazy("CDD Specialist").__str__()
        if user.groups.filter(name="Accountant").exists():
            return gettext_lazy("Accountant").__str__()
        if user.groups.filter(name="Infra").exists():
            return gettext_lazy("Infra").__str__()
        if user.groups.filter(name="Supervisor").exists():
            return gettext_lazy("Supervisor").__str__()
        
        if user.groups.filter(name="Validator").exists():
            return gettext_lazy("Validator").__str__()


    return gettext_lazy("User").__str__()

@register.filter(name='get_to_percent_str') 
def get_to_percent_str(number):
    return str(number if number >= 10 else "0"+str(number)) + " %"

@register.filter
def replace_comma_by_dot(value):
    return str(value).replace(",",".")

@register.filter(name='sort')
def listsort(value):
    return sorted(value)

# @register.filter
# def join(_list: list, separator: str):
#     return separator.join(_list)

@register.filter
def join_attr(_list: list, attr: str):
    return ", ".join([v[attr] for v in _list])

@register.filter
def administrative_regions_objects_names(value):
    return ", ".join([elt['name'] for v in value for elt in v['villages']])

@register.filter
def administrative_regions_objects(value):
    cantons = [c['name'] for c in value]
    villages = [elt['name'] for v in value for elt in v['villages']]
    return {
        'villages': ", ".join(villages),
        'villages_numbers': len(villages),
        'cantons': ", ".join(cantons),
        'cantons_numbers': len(cantons)
    }

@register.filter
def get_facilitator_by_email(facilitator):
    return Facilitator.objects.filter(email=(((facilitator.get('representative').get('email') if facilitator.get('representative') else None) if facilitator.get('representative') else None) if facilitator else None)).first()



@register.filter
def last_facilitator_cdd(adl, request):
    last_assign = mis_objects_call.filter_objects(
        AssignAdministrativeLevelToFacilitator,
        administrative_level_id=adl.id,
        project_id=request.session.get("project_mis_id")
    ).last()

    if last_assign:
        return Facilitator.objects.filter(id=last_assign.facilitator_id).first()
    
    return None

@register.filter
def percent_cdd(adl, request):
    totals = AggregatedStatus.objects.filter(
        administrative_level_id=adl.id,
        project__id=request.session.get("project_id"),
        cycle__id=request.session.get("cycle_id"),
        task=None,
        facilitator=None
    ).aggregate(
        total_tasks_completed=Sum('total_tasks_completed'),
        total_tasks=Sum('total_tasks')
    )

    t_t_c = totals.get('total_tasks_completed') or 0
    t_t = totals.get('total_tasks') or 0

    if t_t > 0:
        return round((t_t_c / t_t) * 100, 2)

    return None

@register.filter
def last_activity_cdd(adl, request):
    try:
        return AggregatedStatus.objects.filter(
            administrative_level_id=adl.id,
            project__id=request.session.get("project_id"),
            cycle__id=request.session.get("cycle_id"),
            task=None,
            facilitator=None
        ).latest('last_activity').last_activity
    except AggregatedStatus.DoesNotExist:
        return None

@register.filter
def detail_cdd_activity(adl, request):
    aggregs = AggregatedStatus.objects.filter(
        administrative_level_id=adl.id,
        project__id=request.session.get("project_id"),
        cycle__id=request.session.get("cycle_id"),
        task=None,
        facilitator=None
    )

    if aggregs.exists():
        totals = aggregs.aggregate(
            total_tasks_completed=Sum('total_tasks_completed'),
            total_tasks=Sum('total_tasks')
        )

        t_t_c = totals['total_tasks_completed'] or 0
        t_t = totals['total_tasks'] or 1
        
        _percent_cdd = round((t_t_c / t_t) * 100, 2)

        return {
            "percent_cdd": _percent_cdd,
            "last_activity_cdd": aggregs.latest('last_activity') #.last_activity
        }

    return {"percent_cdd": None, "last_activity_cdd": None}
# def detail_cdd_activity(adl, request):
#     _last_activity_cdd = None
#     _percent_cdd = None
#     aggregs = AggregatedStatus.objects.filter(
#         administrative_level_id=adl.id, project__id=request.session.get("project_id"), 
#         cycle__id=request.session.get("cycle_id"), task=None, facilitator=None
#     )
#     print(aggregs)
#     t_t_c = aggregs.aggregate(Sum('total_tasks_completed'))['total_tasks_completed__sum']
#     t_t = aggregs.aggregate(Sum('total_tasks'))['total_tasks__sum']
#     if aggregs.exists():
#         _percent = t_t_c/t_t if t_t else 0
#         _percent_cdd = float("%.2f" % ((_percent if _percent else 0)*100))

#         _last_activity_cdd = aggregs.order_by('last_activity').last()

#     return {
#         "percent_cdd": _percent_cdd,
#         "last_activity_cdd": _last_activity_cdd
#     }

@register.filter
def facilitator_on_this_cvd(adl, request):
    return mis_objects_call.filter_objects(AssignAdministrativeLevelToFacilitator,
        administrative_level_id=adl.id,
        project_id=request.session.get("project_mis_id"),
        activated=True
    ).exists()


@register.filter
def check_if_activity_is_enable_to_report(activity, user):
    activity_user = activity.get('user') if activity.get('user') else activity.get('facilitator')
    return (
             activity_user and (activity_user.get('email') == user.email or  activity_user.get('username') == user.username) and 
             activity.get('validated') and 
            (
                not (activity.get('completed') or activity.get('is_another') or activity.get('undo'))
            )
        )

@register.filter
def check_if_activity_is_for_user_auth(activity, user):
    activity_user = activity.get('user') if activity.get('user') else activity.get('facilitator')
    return (
             activity_user and (activity_user.get('email') == user.email or  activity_user.get('username') == user.username)
        )

@register.filter
def check_if_activity_is_enable_to_validate(activity, user):
    if isinstance(activity, dict):
        activity = PlanActivity.objects.get(id=activity.get('id'))

    user_auth_groups = set(user.groups.values_list('id', flat=True))

    if activity.user:
        user_planner_groups = set(activity.user.groups.values_list('id', flat=True))
    else:
        user_planner_groups = set(Group.objects.filter(name="Facilitator").values_list('id', flat=True))

    return ValidationGroupsProcess.objects.filter(
        planners_groups__in=user_planner_groups,
        validators_groups__in=user_auth_groups,
        project__in=user.projects.all()
    ).exists()
# def check_if_activity_is_enable_to_validate(activity, user):
#     activity = PlanActivity.objects.get(id=activity.get('id'))
#     user_auth_groups = [g.id for g in user.groups.all()]

#     user_planner_groups = [g.id for g in Group.objects.filter(name="Facilitator")]
#     if activity.user:
#         user_planner_groups = [g.id for g in activity.user.groups.all()]
        
#     return ValidationGroupsProcess.objects.filter(
#         planners_groups__in=user_planner_groups,
#         validators_groups__in=user_auth_groups,
#         project__in=user.projects.all()
#     ).exists()


@register.filter
def check_if_user_auth_is_in_project(user, project_id):
    return user.projects.filter(id=project_id).exists()