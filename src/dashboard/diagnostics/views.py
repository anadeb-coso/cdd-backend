from django.views.generic import FormView, View as GenericView
from django.contrib.auth.mixins import LoginRequiredMixin
from dashboard.mixins import PageMixin, AJAXRequestMixin, JSONResponseMixin
from django.utils.translation import gettext_lazy
from django.conf import settings
from dashboard.diagnostics.forms import DiagnosticsForm
from dashboard.utils import (
    get_child_administrative_levels, get_parent_administrative_level, 
    get_documents_by_type, get_administrative_levels_by_type,
    get_region_of_village_by_sql_id, get_all_docs_administrative_levels_by_type_and_administrative_id,
    get_all_docs_administrative_levels_by_type_and_parent_id
)
from no_sql_client import NoSQLClient
from authentication.models import Facilitator
from dashboard.administrative_levels.functions import (get_cascade_villages_by_administrative_level_id,
                                                       get_administrative_level_under_json)
from administrativelevels import models as administrativelevels_models
from dashboard.facilitators.functions import get_cvds
from process_manager.models import Task, Phase, Activity
from cdd import functions as cdd_functions

class DashboardDiagnosticsCDDView(PageMixin, LoginRequiredMixin, FormView):
    
    template_name = 'diagnostics/diagnostics.html'
    context_object_name = 'Diagnostics'
    title = gettext_lazy('diagnostics')
    active_level1 = 'diagnostics'
    form_class = DiagnosticsForm
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['access_token'] = settings.MAPBOX_ACCESS_TOKEN
        context['lat'] = settings.DIAGNOSTIC_MAP_LATITUDE
        context['lng'] = settings.DIAGNOSTIC_MAP_LONGITUDE
        context['zoom'] = settings.DIAGNOSTIC_MAP_ZOOM
        context['ws_bound'] = settings.DIAGNOSTIC_MAP_WS_BOUND
        context['en_bound'] = settings.DIAGNOSTIC_MAP_EN_BOUND
        context['country_iso_code'] = settings.DIAGNOSTIC_MAP_ISO_CODE

        context['list_fields'] = ["phase", "activity", "task", "region", "prefecture", "commune", "canton", "village"]

        return context

    def render_to_response(self, context, **response_kwargs):
        """
        Return a response, using the `response_class` for this view, with a
        template rendered with the given context.
        Pass response_kwargs to the constructor of the response class.
        """
        response_kwargs.setdefault('content_type', self.content_type)
        return self.response_class(
            request=self.request,
            template=self.get_template_names(),
            context=context,
            using=self.template_engine,
            **response_kwargs
        )
    




class GetTasksDiagnosticsView(AJAXRequestMixin, LoginRequiredMixin, JSONResponseMixin, GenericView):
    def get(self, request, *args, **kwargs):
        _type = request.GET.get('type')
        type_header = _type
        sql_id = request.GET.get('sql_id')
        if not sql_id:
            raise Exception("The value of the element must be not null!!!")
        nsc = NoSQLClient()
        # administrative_levels_db = nsc.get_db("administrative_levels")
        
        liste_villages = []
        nbr_tasks = 0
        nbr_tasks_completed = 0
        percentage_tasks_completed = 0
        nbr_facilitators = 0
        nbr_villages = 0
        nbr_cvds = 0
        search_by_locality = False
        already_count_facilitator = False
        _region = None
        regions = {
            # "SAVANES": {
            #     "nbr_tasks": 0,
            #     "nbr_tasks_completed": 0,
            #     "percentage_tasks_completed": 0
            # }, 
            # "KARA":{
            #     "nbr_tasks": 0,
            #     "nbr_tasks_completed": 0,
            #     "percentage_tasks_completed": 0
            # }, 
            # "CENTRALE":{
            #     "nbr_tasks": 0,
            #     "nbr_tasks_completed": 0,
            #     "percentage_tasks_completed": 0
            # }
        }

        if _type in ["region", "prefecture", "commune", "canton", "village"]:
            search_by_locality = True
            # liste_prefectures = []
            # liste_communes = []
            # liste_cantons = []
            # administrative_levels = administrative_levels_db.all_docs(include_docs=True)['rows']

            # if _type == "region":
            ##     region = get_all_docs_administrative_levels_by_type_and_administrative_id(administrative_levels, _type.title(), sql_id)
            ##     region = region[:][0]
            #     _type = "prefecture"
            #     liste_prefectures = get_all_docs_administrative_levels_by_type_and_parent_id(administrative_levels, _type.title(), region['administrative_id'])[:]
                    
            # if _type == "prefecture":
            #     if not liste_prefectures:
            #         liste_prefectures = get_all_docs_administrative_levels_by_type_and_administrative_id(administrative_levels, _type.title(), sql_id)[:]
            #     _type = "commune"
            #     for prefecture in liste_prefectures:
            #         [liste_communes.append(elt) for elt in get_all_docs_administrative_levels_by_type_and_parent_id(administrative_levels, _type.title(), prefecture['administrative_id'])[:]]

            # if _type == "commune":
            #     if not liste_communes:
            #         liste_communes = get_all_docs_administrative_levels_by_type_and_administrative_id(administrative_levels, _type.title(), sql_id)[:]
            #     _type = "canton"
            #     for commune in liste_communes:
            #         [liste_cantons.append(elt) for elt in get_all_docs_administrative_levels_by_type_and_parent_id(administrative_levels, _type.title(), commune['administrative_id'])[:]]

            # if _type == "canton":
            #     if not liste_cantons:
            #         liste_cantons = get_all_docs_administrative_levels_by_type_and_administrative_id(administrative_levels, _type.title(), sql_id)[:]
            #     _type = "village"
            #     for canton in liste_cantons:
            #         [liste_villages.append(elt) for elt in get_all_docs_administrative_levels_by_type_and_parent_id(administrative_levels, _type.title(), canton['administrative_id'])[:]]
            
            # if _type == "village":
            #     if not liste_villages:
            #         liste_villages = get_all_docs_administrative_levels_by_type_and_administrative_id(administrative_levels, _type.title(), sql_id)[:]
            liste_villages = get_cascade_villages_by_administrative_level_id(int(sql_id))
            
            for f in Facilitator.objects.filter(develop_mode=False, training_mode=False):
                already_count_facilitator = False
                facilitator_db = nsc.get_db(f.no_sql_db_name)
                docs = facilitator_db.all_docs(include_docs=True)['rows']
                facilitator_doc = None
                for _doc in docs:
                    doc = _doc.get('doc')
                    if doc.get('type') == 'facilitator' and not doc.get('develop_mode') and not doc.get('training_mode'):
                        facilitator_doc = doc
                        break
                # query_result = facilitator_db.get_query_result({
                #     "type": 'facilitator' #, "develop_mode": False, "training_mode": False
                #     })[:]
                if facilitator_doc:
                    doc = facilitator_doc
                    cvds = get_cvds(doc)
                    for cvd in cvds:
                        _village = cvd['village']
                        for village in liste_villages:
                            if str(_village['id']) == str(village['administrative_id']):
                                nbr_villages += len(cvd['villages'])
                                nbr_cvds += 1
                                if not already_count_facilitator:
                                    nbr_facilitators += 1
                                    already_count_facilitator = True
                                    
                                for _task in docs:
                                    _task = _task.get('doc')
                                    if _task.get('type') == 'task' and str(_task.get('administrative_level_id')) == str(_village['id']):
                                        if _task['completed']:
                                            nbr_tasks_completed += 1
                                        nbr_tasks += 1
                                
            # nbr_villages = len(liste_villages)      
            if nbr_villages > 0:
                ad_obj = administrativelevels_models.AdministrativeLevel.objects.using('mis').get(id=int(liste_villages[0]['administrative_id']))
                _region = get_administrative_level_under_json(
                    ad_obj.parent.parent.parent.parent
                )
                

            percentage_tasks_completed = ((nbr_tasks_completed/nbr_tasks)*100) if nbr_tasks else 0

        elif _type in ["phase", "activity", "task"]:
            # if _type in ("phase", 'activity'):
            tasks = []
            if _type == "phase":
                tasks = Phase.objects.get(id=int(sql_id)).task_set.get_queryset()
            elif _type == "activity":
                tasks = Activity.objects.get(id=int(sql_id)).task_set.get_queryset()
            elif _type == "task":
                tasks.append(Task.objects.get(id=int(sql_id)))
            
            for f in Facilitator.objects.filter(develop_mode=False, training_mode=False):
                already_count_facilitator = False
                facilitator_db = nsc.get_db(f.no_sql_db_name)
                # query_result = facilitator_db.get_query_result({"type": _type, "sql_id": int(sql_id)})[:]
                docs = facilitator_db.all_docs(include_docs=True)['rows']
                facilitator_doc = None
                for _doc in docs:
                    doc = _doc.get('doc')
                    if doc.get('type') == 'facilitator' and not doc.get('develop_mode') and not doc.get('training_mode'):
                        facilitator_doc = doc
                        break
                    
                if facilitator_doc:
                    
                    cvds = get_cvds(facilitator_doc)
                    for cvd in cvds:
                        _village = cvd['village']
                        nbr_villages += len(cvd['villages'])
                        ad_obj = administrativelevels_models.AdministrativeLevel.objects.using('mis').get(id=int(_village['id']))
                        print(ad_obj, _village['name'], ad_obj.id, _village['id'], f.no_sql_db_name)
                        try:
                            _region = get_administrative_level_under_json(
                                ad_obj.parent.parent.parent.parent
                            )
                            nbr_cvds += 1
                            for _task in docs:
                                _task = _task.get('doc')
                                if _task.get('type') == 'task' and _task.get('sql_id') and cdd_functions.exists_id(tasks, int(_task.get('sql_id'))) and str(_village['id']) == str(_task['administrative_level_id']):
                                
                                    if not already_count_facilitator:
                                        nbr_facilitators += 1
                                        already_count_facilitator = True

                                    
                                    if _region:
                                        _region_name = _region['name']
                                        if regions.get(_region_name):
                                            if _task['completed']:
                                                regions[_region_name]["nbr_tasks_completed"] += 1
                                            regions[_region_name]["nbr_tasks"] += 1
                                        else:
                                            regions[_region_name] = {
                                                "nbr_tasks": 1,
                                                "nbr_tasks_completed": 1 if _task['completed'] else 0,
                                                "percentage_tasks_completed": 0,
                                                "nbr_cvds": 0,
                                                "nbr_villages": 0
                                            }
                                        if _task['completed']:
                                            nbr_tasks_completed += 1
                                        nbr_tasks += 1
                            
                            if _region:
                                _region_name = _region['name']
                                regions[_region_name]["nbr_villages"] += len(cvd['villages'])
                                regions[_region_name]["nbr_cvds"] += 1
                        except Exception as exc:
                            print(exc)
            # elif _type == "task":
            #     for f in Facilitator.objects.filter(develop_mode=False, training_mode=False):
            #         already_count_facilitator = False
            #         facilitator_db = nsc.get_db(f.no_sql_db_name)
            #         _tasks = facilitator_db.get_query_result({"type": 'task', "sql_id": int(sql_id)})[:]
            #         for _task in _tasks:
            #             if str(_task['administrative_level_id']).isdigit():

            #                 if not already_count_facilitator:
            #                     nbr_facilitators += 1
            #                     already_count_facilitator = True

            #                 _region = get_region_of_village_by_sql_id(administrative_levels_db, _task['administrative_level_id'])
            #                 if _region:
            #                     _region_name = _region['name']
            #                     if regions.get(_region_name):
            #                         if _task['completed']:
            #                             regions[_region_name]["nbr_tasks_completed"] += 1
            #                         regions[_region_name]["nbr_tasks"] += 1
                

            for region, values in regions.items():
                regions[region]["percentage_tasks_completed"] = ((regions[region]["nbr_tasks_completed"]/regions[region]["nbr_tasks"])*100) if regions[region]["nbr_tasks"] else 0


        if search_by_locality:
            return self.render_to_json_response({
                "type": type_header.title(), 
                "nbr_tasks": nbr_tasks,
                "nbr_tasks_completed": nbr_tasks_completed,
                "percentage_tasks_completed": percentage_tasks_completed,
                "region": _region["name"] if _region else None,
                "search_by_locality": search_by_locality,
                "nbr_facilitators": nbr_facilitators,
                "nbr_villages": nbr_villages,
                "nbr_cvds": nbr_cvds
            }, safe=False)
        
        return self.render_to_json_response({
            "type": type_header, 
            "regions": regions,
            "search_by_locality": search_by_locality,
            "nbr_facilitators": nbr_facilitators,
            "nbr_villages": nbr_villages,
            "nbr_cvds": nbr_cvds,
            "nbr_tasks": nbr_tasks,
            "nbr_tasks_completed": nbr_tasks_completed,
        }, safe=False)