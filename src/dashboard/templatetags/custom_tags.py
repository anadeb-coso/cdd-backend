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
from grm_client import attach_administrative_regions_objects

register = template.Library()


@register.filter
def get(dictionary, key):
    return dictionary.get(key, None)

@register.filter
def get_set_item(set_data: set, key):
    try:
        return set_data[int(key)]
    except Exception as exc:
        return None

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



def _field_config(config, field):
    try:
        return config.get(field) or {}
    except AttributeError:
        return {}


def _nested_config(sub_config):
    # Dict-type fields describe their sub-fields under "fields" (+ leur ordre
    # d'affichage sous "order") ; list-type fields (répétable) les décrivent
    # sous "item.fields" (+ "item.order") — même convention que le form
    # builder web / le moteur mobile (task_form_builder.js `orderedKeys`,
    # cdd-form-logic.js `applyFieldOrder`) : `options.order` existe
    # spécifiquement parce que le stockage JSON (jsonb Postgres / CouchDB) ne
    # garantit pas de conserver l'ordre de saisie des clés d'un objet.
    if not isinstance(sub_config, dict):
        return {}, None
    nested = sub_config.get('fields')
    if nested:
        return nested, sub_config.get('order')
    item = sub_config.get('item') or {}
    return item.get('fields') or {}, item.get('order')


def _ordered_keys(keys, order):
    """`keys` (vue dict, ordre non garanti pertinent) réordonnées selon
    `order` (liste de clés telle que configurée dans le Générateur de
    formulaire) quand disponible ; les clés absentes de `order` (champ
    ajouté au formulaire après une réponse déjà enregistrée, formulaire
    legacy sans `order`, etc.) sont ajoutées à la suite, dans leur ordre
    d'origine — jamais perdues."""
    keys = list(keys)
    if not order:
        return keys
    key_set = set(keys)
    ordered = [k for k in order if k in key_set]
    ordered_set = set(ordered)
    ordered.extend(k for k in keys if k not in ordered_set)
    return ordered


def _sub_schema_props(prop):
    """JSON-schema `properties` enfant d'un schéma object / array<object> —
    mirroir de `dashboard.process_manager.tasks.form_design._sub_properties`,
    dupliqué ici (6 lignes) plutôt qu'importé pour ne pas coupler ce module
    d'affichage aux internes du form builder."""
    if not isinstance(prop, dict):
        return None
    if prop.get('type') == 'object':
        return prop.get('properties') or {}
    if prop.get('type') == 'array':
        items = prop.get('items') or {}
        if isinstance(items, dict) and items.get('type') == 'object':
            return items.get('properties') or {}
    return None


def _enum_label_map(prop):
    """Mapping valeur -> libellé d'un champ select (`prop['enum']` pour
    select_one, `prop['items']['enum']` pour select_multiple/check) SI c'est
    un dict — cas d'une source dynamique db/excel/admin_levels (champ
    "Modèle" type AdministrativeLevel/CVD : la valeur stockée est un
    identifiant technique, pas le libellé humain, cf. `compileSelectSchema`
    `isDynamicSource` côté `task_form_builder.js`). `None` pour une liste
    statique (`enum` = liste, valeur == libellé, rien à résoudre) ou un champ
    non-select — dans ces cas la valeur brute est déjà ce qu'il faut afficher."""
    if not isinstance(prop, dict):
        return None
    target = prop
    if prop.get('type') == 'array':
        items = prop.get('items')
        target = items if isinstance(items, dict) else {}
    enum = target.get('enum') if isinstance(target, dict) else None
    return enum if isinstance(enum, dict) else None


def _resolve_display_value(value, prop):
    """Remplace la/les valeur(s) stockée(s) d'un champ select par son/leurs
    libellé(s) humain(s) quand connu (`_enum_label_map`) — sinon renvoie
    `value` inchangée (comportement historique, y compris pour les groupes/
    répétables, dont le schéma n'a jamais d'`enum`)."""
    label_map = _enum_label_map(prop)
    if not label_map:
        return value
    if isinstance(value, list):
        return [label_map.get(str(v), v) for v in value]
    return label_map.get(str(value), value)


def _structure_value(value, config, order=None, schema_props=None):
    """Recursively re-shape a form_response value into {'name', 'value'} nodes,
    resolving each field's label from the form's field configuration at every
    depth, ordering keys per `order` (cf. `_ordered_keys`), and resolving
    select values to their human label per `schema_props` (cf.
    `_resolve_display_value`)."""
    config = config or {}
    schema_props = schema_props if isinstance(schema_props, dict) else {}
    if type(value) == dict:
        result = {}
        for field in _ordered_keys(value.keys(), order):
            sub_value = value[field]
            sub_config = _field_config(config, field)
            label = sub_config.get('label')
            nested_fields, nested_order = _nested_config(sub_config)
            prop = schema_props.get(field)
            sub_value = _resolve_display_value(sub_value, prop)
            result[field] = {
                'name': label if label else utils_structure_the_words(field),
                'value': _structure_value(sub_value, nested_fields, nested_order, _sub_schema_props(prop)),
            }
        return result
    if type(value) == list:
        return [_structure_value(item, config, order, schema_props) for item in value]
    return value


@register.filter(name="structureTheFieldsLabels")
def structure_the_fields_labels(task):
    fields_values = []
    if task.get("form_response"):
        form = task.get("form") or []
        for i, fields in enumerate(task.get("form_response")):
            page = form[i] if i < len(form) and isinstance(form[i], dict) else {}
            page_options = page.get('options') or {}
            fields_options = page_options.get('fields') or {}
            top_order = page_options.get('order')
            schema_props = (page.get('page') or {}).get('properties') or {}
            if not isinstance(schema_props, dict):
                schema_props = {}
            dict_values = {}
            for field in _ordered_keys(fields.keys(), top_order):
                value = fields[field]
                prop = schema_props.get(field)
                value = _resolve_display_value(value, prop)
                sub_config = _field_config(fields_options, field)
                label = sub_config.get('label')
                if type(value) == dict:
                    value = order_dict(task.get('sql_id'), field, value)
                nested_fields, nested_order = _nested_config(sub_config)
                dict_values[field] = {
                    'name': label if label else utils_structure_the_words(field),
                    'value': _structure_value(value, nested_fields, nested_order, _sub_schema_props(prop)),
                }
            fields_values.append(dict_values)
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

@register.filter(name="attachmentLocationLabel")
def attachment_location_label(attachment):
    """Nom du canton si le libellé de la pièce jointe ("document du plan
    d'actions cantonales finalisé", etc.) évoque un canton, sinon nom du
    village siège — même règle que le titre de carte de la galerie
    documents (`administrative_levels/documents/_grid.html`). Réutilisé pour
    nommer le fichier au téléchargement (individuel et groupé)."""
    if not attachment:
        return ""
    name = attachment.get("name") if hasattr(attachment, "get") else getattr(attachment, "name", "")
    if "canton" in str(name or "").lower():
        value = attachment.get("canton") if hasattr(attachment, "get") else getattr(attachment, "canton", "")
    else:
        value = attachment.get("headquarters_village") if hasattr(attachment, "get") else getattr(attachment, "headquarters_village", "")
    return value or ""

@register.filter(name="attachmentDownloadFilename")
def attachment_download_filename(attachment, raw_url):
    """``"<intitulé de la pièce jointe> (<village/canton>)<extension>"`` —
    nom de fichier proposé au téléchargement (individuel, lien
    `download_from_url?filename=...` ; groupé, `views_doc.
    DownloadAttachmentsZipView`, même logique en Python côté serveur)."""
    from cdd.my_librairies.download_file import display_filename_with_suffix
    if not attachment:
        return "fichier"
    name = attachment.get("name") if hasattr(attachment, "get") else getattr(attachment, "name", "")
    return display_filename_with_suffix(name or "fichier", attachment_location_label(attachment), raw_url)

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
        etc.
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
        
        if user.groups.filter(name="YouthProgramSpecialist").exists():
            return gettext_lazy("Youth Program Specialist").__str__()
        if user.groups.filter(name="LocalEconomicDevelopmentSpecialist").exists():
            return gettext_lazy("Local Economic Development Specialist").__str__()
        if user.groups.filter(name="CommunicationSpecialist").exists():
            return gettext_lazy("Communication Specialist").__str__()
        if user.groups.filter(name="CommunityFacilitator").exists():
            return gettext_lazy("Community Facilitator").__str__()
        if user.groups.filter(name="TechnicalFacilitator").exists():
            return gettext_lazy("Technical Facilitator").__str__()
        
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

@register.filter(name='attach_administrative_regions_objects') 
def filter_attach_administrative_regions_objects(value):
    
    value = attach_administrative_regions_objects(value or [])['administrative_regions_objects']

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
    elif activity.facilitator:
        if activity.facilitator.facilitator_type == "community_facilitator":
            user_planner_groups = set(Group.objects.filter(name="CommunityFacilitator").values_list('id', flat=True))
        elif activity.facilitator.facilitator_type == "technical_facilitator":
            user_planner_groups = set(Group.objects.filter(name="TechnicalFacilitator").values_list('id', flat=True))
    if not user_planner_groups and user_auth_groups:
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


@register.filter
def separate_with_space(value, unit=None, show_float=False):
    if unit:
        unit = " " + unit
    else:
        unit = ""
    
    if not show_float and value:
        value = round(float(value))

    if value != 0 and (not value or not str(value).replace('-','').replace('.','',1).replace(',','',1).isdigit()):
        return ""
    

    float_values = str(value).split(',')
    if len(float_values) > 1:
        float_value = float_values[-1]
    else:
        float_value = float_values[0]
    float_values = str(float_value).split('.')
    if len(float_values) > 1:
        float_value = float_values[-1]
    else:
        float_value = None



    value = str(value).split(',')[0].split('.')[0]
    l = len(str(int(value)))
    if l in (0, 1) and int(value) < 1:
        return str(int(value)) + unit
    
    list_value_str = list(value)
    list_value_str.reverse()
    money_format = ""
    for i in range(1, len(list_value_str)+1):
        money_format += list_value_str[i-1]
        if i%3 == 0 :
            money_format += " "

    list_money_format = list(money_format)
    list_money_format.reverse()

    return "".join(list_money_format) + "." + float_value + unit if float_value else "".join(list_money_format) + unit
