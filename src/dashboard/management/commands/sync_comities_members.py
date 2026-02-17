from django.core.management.base import BaseCommand, CommandError

from no_sql_client import NoSQLClient
from administrativelevels.models import AdministrativeLevel
from cdd.utils import check_for_valid_facilitator
from cdd.call_objects_from_other_db import mis_objects_call
from reports.models import VillageCommittee
from dashboard.tasks import bulk_objects_create_or_update

class Command(BaseCommand):

    

    def handle(self, *args, **options):
        # Your command logic here
        sync_comities_members()
                
        self.stdout.write(self.style.SUCCESS('Successfully executed mycommand!'))


def sync_comities_members():
    nsc = NoSQLClient()
    facilitator_dbs = nsc.list_all_databases('facilitator')

    tasks_name = [
        "Mise en place et/ou restructuration du CVD (B/CVD, CS,  et les commissions spécialisées : CTMO, CCT, CES, Election de deux 02 représentants des jeunes et du CVGP. )", # COSO, PURS
        "Mise en place et/ou restructuration du CVD (B/CVD, CS,  et les commissions spécialisées : CTMO, CCT, CES, Election des membres du comité villageois de jeunesse, CIRDI )", # COSO
    ]
    tasks_id = [
        29, # COSO
        78, # PURS
        114, # FA-COSO
    ]
    village_committees_bulk_create_list = []
    village_committees_bulk_update_list = []

    for db_name in facilitator_dbs:
        if check_for_valid_facilitator(nsc, db_name):
            db = nsc.get_db(db_name).get_query_result({
                "type": "task",
                "$or": [
                    {
                        "name": {"$in": tasks_name}
                    },
                    {
                        "sql_id": {"$in": tasks_id}
                    }
                ]
            })
            response = None
            for document in db:
                response = get_and_update_comities_members(document)
                if response:
                    (
                        cvd_id, 
                        cvd_name,
                        village_headquarters_id, 
                        village_headquarters_name,
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
                        village_committee.members = committee_members
                        village_committee.number_of_members = len(committee_members)
                        village_committee.members_included_women = members_included_women
                        village_committee.method_used_to_select_members = method_used_to_select_members

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
            'members',
            'number_of_members',
            'members_included_women',
            'method_used_to_select_members'
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
            administrative_level.parent.name if administrative_level.parent else None,
            administrative_level.parent.parent.name if administrative_level.parent and administrative_level.parent.parent else None,
            administrative_level.parent.parent.parent.name if administrative_level.parent and administrative_level.parent.parent and administrative_level.parent.parent.parent else None,
            administrative_level.parent.parent.parent.parent.name if administrative_level.parent and administrative_level.parent.parent and administrative_level.parent.parent.parent and administrative_level.parent.parent.parent.parent else None,
            document['project_name'],
            comittes_response,
            method_used_to_select_members
        )
    
    return None

