from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from no_sql_client import NoSQLClient
from administrativelevels.models import AdministrativeLevel
from cdd.utils import check_for_valid_facilitator
from cdd.call_objects_from_other_db import mis_objects_call
from reports.models import VillageCommittee
from dashboard.tasks import bulk_objects_create_or_update
from cdd.functions import datetime_complet_str

class Command(BaseCommand):

    

    def handle(self, *args, **options):
        # Your command logic here
        sync_comities_members()
                
        self.stdout.write(self.style.SUCCESS('Successfully executed mycommand!'))


def sync_comities_members():
    nsc = NoSQLClient()
    facilitator_dbs = nsc.list_all_databases('facilitator')
    now = timezone.now()

    tasks_name = [
        "Mise en place et/ou restructuration du CVD (B/CVD, CS,  et les commissions spécialisées : CTMO, CCT, CES, Election de deux 02 représentants des jeunes et du CVGP. )", # COSO, PURS
        "Mise en place et/ou restructuration du CVD (B/CVD, CS,  et les commissions spécialisées : CTMO, CCT, CES, Election des membres du comité villageois de jeunesse, CIRDI )", # FA-COSO
    ]
    tasks_name_for_date = [
        "Ouverture de la deuxième réunion et vérification du quorum des participants"
    ]
    tasks_name_for_checking_cvd = [
        "Vérification de l'existence du CVD et de ses organes"
    ]

    tasks_id = [
        29, # COSO
        78, # PURS
        114, # FA-COSO
    ]
    tasks_id_for_date = [
        27, # COSO
        76, # PURS
        112, #FA-COSO
    ]
    tasks_id_for_checking_cvd = [
        19, # COSO
        68, # PURS
        104, # FA-COSO
    ]

    village_committees_bulk_create_list = []
    village_committees_bulk_update_list = []

    for db_name in facilitator_dbs:
        if check_for_valid_facilitator(nsc, db_name):
            _query_result = nsc.get_db(db_name).get_query_result({
                "type": "task",
                "$or": [
                    {
                        "name": {"$in": tasks_name + tasks_name_for_date + tasks_name_for_checking_cvd}
                    },
                    {
                        "sql_id": {"$in": tasks_id + tasks_id_for_date + tasks_id_for_checking_cvd}
                    }
                ]
            })
            query_result = [_ for _ in _query_result if _['name'] in tasks_name or _['sql_id'] in tasks_id]
            query_result_for_date = [_ for _ in _query_result if _['name'] in tasks_name_for_date or _['sql_id'] in tasks_id_for_date]
            query_result_checking_cvd = [_ for _ in _query_result if _['name'] in tasks_name_for_checking_cvd or _['sql_id'] in tasks_id_for_checking_cvd]
            
            response = None
            for document in query_result:
                response = get_and_update_comities_members(document)
                if response:
                    (
                        cvd_id, 
                        cvd_name,
                        village_headquarters_id, 
                        village_headquarters_name,
                        villages_ids,
                        villages_names,
                        canton_headquarters,
                        commune_headquarters,
                        prefecture_headquarters,
                        region_headquarters,
                        project_name,
                        comittes_response,
                        method_used_to_select_members
                    ) = response
                    for comitte, comitte_info in comittes_response.items():
                        committee_members = comitte_info.get('members', {})
                        committee_description = comitte_info.get('description', "")
                        members_included_women = comitte_info.get('members_included_women', False)

                        village_committee = VillageCommittee.objects.filter(
                            name=comitte,
                            cvd_id=cvd_id, 
                            project_name=project_name
                        ).first()
                        _action = 'updated'
                        if not village_committee:
                            village_committee = VillageCommittee()
                            village_committee.name = comitte
                            village_committee.cvd_id = cvd_id
                            village_committee.project_name = project_name
                            village_committee.canton = canton_headquarters
                            village_committee.commune = commune_headquarters
                            village_committee.prefecture = prefecture_headquarters
                            village_committee.region = region_headquarters
                            village_committee.description = committee_description
                            _action = 'created'
                            
                        village_committee.cvd_name = cvd_name
                        village_committee.village_headquarters_id = village_headquarters_id
                        village_committee.village_headquarters_name = village_headquarters_name
                        village_committee.villages_ids = villages_ids
                        village_committee.villages_names = villages_names
                        village_committee.members = committee_members
                        village_committee.number_of_members = len(committee_members)
                        village_committee.members_included_women = members_included_women
                        village_committee.method_used_to_select_members = method_used_to_select_members
                        village_committee.updated_date = now
                        
                        checking_cvd_tasks = [_ for _ in query_result_checking_cvd if _['administrative_level_id'] == document['administrative_level_id'] and _['project_name'] == document['project_name']]
                        try:
                            cvd_existence = checking_cvd_tasks[0].get('form_response', [{}])[0].get('structuration', {}).get('existenCVD') if checking_cvd_tasks else None
                        except:
                            cvd_existence = None
                        village_committee.cvd_existence = (True if cvd_existence == 'Oui' else False) if cvd_existence else None

                        try:
                            full_staff = checking_cvd_tasks[0].get('form_response', [{}])[0].get('structuration', {}).get('effectifComplet') if checking_cvd_tasks else None
                        except:
                            full_staff = None
                        village_committee.is_full_staff = (True if full_staff == 'Oui' else False) if full_staff else None
                        
                        try:
                            open_second_meeting_tasks = [_ for _ in query_result_for_date if _['administrative_level_id'] == document['administrative_level_id'] and _['project_name'] == document['project_name']]
                            date_str = open_second_meeting_tasks[0].get('form_response', [{}])[0].get('dateDeLaReunion') if open_second_meeting_tasks else None
                        except:
                            date_str = None
                        village_committee.meeting_date = date_str if date_str else None
                        
                        
                        if _action == 'created':
                            village_committees_bulk_create_list.append(village_committee)
                        else:
                            village_committees_bulk_update_list.append(village_committee)
    
    if village_committees_bulk_create_list:
        bulk_objects_create_or_update(VillageCommittee, village_committees_bulk_create_list, type_bulk="create")
    if village_committees_bulk_update_list:
        bulk_objects_create_or_update(VillageCommittee, village_committees_bulk_update_list, type_bulk="update", fields=[
            'cvd_name',
            'village_headquarters_id',
            'village_headquarters_name',
            'villages_ids',
            'villages_names',
            'members',
            'number_of_members',
            'members_included_women',
            'method_used_to_select_members',
            'cvd_existence',
            'is_full_staff',
            'meeting_date',
            'updated_date'
        ])


def get_and_update_comities_members(document):
    print(document['administrative_level_id'])
    adm_id = document['administrative_level_id']
    administrative_levels = mis_objects_call.filter_objects(AdministrativeLevel, id=adm_id)

    if administrative_levels.exists():
        method_used_to_select_members = None
        administrative_level = administrative_levels.first()
        
        comittes_response = {}
        if 'form_response' in document and document.get('form_response'):
            for _ in document['form_response']:
                if "methodeUtilisee" in _:
                    method_used_to_select_members = _["methodeUtilisee"]
                else:
                    for comitte, comitte_description in {
                        'BCVD': 'Bureau du Comité Villageois de Développement (B/CVD)', 
                        'CS': 'Comité de surveillance (CS)', 
                        'CTMO': 'Commission Technique de Mise en Oeuvre (CTMO)', 
                        'CCT': 'Commission Communication et Transparence (CCT)', 
                        'CES': 'Commission Environnementale et Sociale (CES)', 
                        'CVGP': 'Comité Villageoise de Gestion des Plaintes (CVGP)', 
                        'jeunesRepresentant': 'Representant des jeunes (Comité villageois de jeunesse)', 
                        'CIRDI': "Commission en charge de l'Inclusion des Réfugiés et des Déplacés Internes (CIRDI)"
                    }.items():
                        comitte_response = {}
                        members_included_women = False
                        try:
                            if comitte in _:
                                comitte_data = _[comitte]
                                if isinstance(comitte_data, dict):
                                    for role, member_info in comitte_data.items():

                                        if role == 'femmesLeaders':
                                            role = 'femmeLeader'
                                            members_included_women = True
                                            for f_i in range(1, 3):
                                                comitte_response[f"femmeLeader{f_i}"] = {
                                                    "name": f'{member_info.get(f"{role}Nom{f_i}", "")} {member_info.get(f"{role}Prenom{f_i}", "")}'.strip(),
                                                    "genre": member_info.get(f"{role}Genre{f_i}", "Femme"),
                                                    "contact": member_info.get(f"{role}Contact{f_i}", "")
                                                }
                                        else:
                                            member_name = f'{member_info.get(f"{role}Nom", "")} {member_info.get(f"{role}Prenom", "")}'.strip()
                                            member_genre = member_info.get(f"{role}Genre", "")
                                            member_contact = member_info.get(f"{role}Contact", "")
                                            comitte_response[role] = {
                                                "name": member_name,
                                                "genre": member_genre,
                                                "contact": member_contact
                                            }
                                            if member_genre.lower() == "femme":
                                                members_included_women = True
                                elif isinstance(comitte_data, list):
                                    for idx, member_info in enumerate(comitte_data):
                                        member_name = f'{member_info.get("Nom", "")} {member_info.get("Prenom", "")}'.strip()
                                        member_genre = member_info.get("LeGenre", "")
                                        member_contact = member_info.get("Contact", "")
                                        comitte_response[f'member_{idx+1}'] = {
                                            "name": member_name,
                                            "genre": member_genre,
                                            "contact": member_contact
                                        }
                                        if member_genre.lower() == "femme":
                                            members_included_women = True
                        except:
                            pass
                        if comitte_response:
                            comittes_response[comitte] = {
                                "description": comitte_description,
                                "members": comitte_response,
                                "members_included_women": members_included_women
                            }
        return (
            administrative_level.cvd.id, 
            administrative_level.cvd.name,
            administrative_level.cvd.headquarters_village.id, 
            administrative_level.cvd.headquarters_village.name,
            list(administrative_level.cvd.get_villages().values_list('id', flat=True)),
            list(administrative_level.cvd.get_villages().values_list('name', flat=True)),
            administrative_level.parent.name if administrative_level.parent else None,
            administrative_level.parent.parent.name if administrative_level.parent and administrative_level.parent.parent else None,
            administrative_level.parent.parent.parent.name if administrative_level.parent and administrative_level.parent.parent and administrative_level.parent.parent.parent else None,
            administrative_level.parent.parent.parent.parent.name if administrative_level.parent and administrative_level.parent.parent and administrative_level.parent.parent.parent and administrative_level.parent.parent.parent.parent else None,
            document['project_name'],
            comittes_response,
            method_used_to_select_members
        )
    
    return None

