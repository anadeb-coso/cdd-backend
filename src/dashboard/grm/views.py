from django.views.generic import FormView, View as GenericView
from django.contrib.auth.mixins import LoginRequiredMixin
from dashboard.mixins import PageMixin, AJAXRequestMixin, JSONResponseMixin
from django.utils.translation import gettext_lazy
from django.conf import settings
from dashboard.grm.forms import DiagnosticsForm
from dashboard.utils import (
    get_child_administrative_levels, get_parent_administrative_level, 
    get_documents_by_type, get_administrative_levels_by_type,
    get_region_of_village_by_sql_id
)
from no_sql_client import NoSQLClient



class DashboardDiagnosticsCDDView(PageMixin, LoginRequiredMixin, FormView):
    
    template_name = 'grm/diagnostics.html'
    context_object_name = 'GRM'
    title = gettext_lazy('GRM')
    active_level1 = 'grm'
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
        administrative_levels_db = nsc.get_db("administrative_levels")
        print("")
        print("NEW")
        liste_villages = []
        nbr_tasks = 0
        nbr_tasks_completed = 0
        percentage_tasks_completed = 0
        search_by_locality = False
        _region = None
        regions = {
            "SAVANES": {
                "nbr_tasks": 0,
                "nbr_tasks_completed": 0,
                "percentage_tasks_completed": 0
            }, 
            "KARA":{
                "nbr_tasks": 0,
                "nbr_tasks_completed": 0,
                "percentage_tasks_completed": 0
            }, 
            "CENTRALE":{
                "nbr_tasks": 0,
                "nbr_tasks_completed": 0,
                "percentage_tasks_completed": 0
            }
        }

        if _type in ["region", "prefecture", "commune", "canton", "village"]:
            search_by_locality = True
            liste_prefectures = []
            liste_communes = []
            liste_cantons = []

            if _type == "region":
                region = get_administrative_levels_by_type(administrative_levels_db, _type.title(), attrs={"administrative_id": sql_id})
                region = region[:][0]
                _type = "prefecture"
                liste_prefectures = get_administrative_levels_by_type(administrative_levels_db, _type.title(), attrs={"parent_id": region['administrative_id']})[:]
                    
            if _type == "prefecture":
                if not liste_prefectures:
                    liste_prefectures = get_administrative_levels_by_type(administrative_levels_db, _type.title(), attrs={"administrative_id": sql_id})[:]
                _type = "commune"
                for prefecture in liste_prefectures:
                    [liste_communes.append(elt) for elt in get_administrative_levels_by_type(administrative_levels_db, _type.title(), attrs={"parent_id": prefecture['administrative_id']})[:]]

            if _type == "commune":
                if not liste_communes:
                    liste_communes = get_administrative_levels_by_type(administrative_levels_db, _type.title(), attrs={"administrative_id": sql_id})[:]
                _type = "canton"
                for commune in liste_communes:
                    [liste_cantons.append(elt) for elt in get_administrative_levels_by_type(administrative_levels_db, _type.title(), attrs={"parent_id": commune['administrative_id']})[:]]

            if _type == "canton":
                if not liste_cantons:
                    liste_cantons = get_administrative_levels_by_type(administrative_levels_db, _type.title(), attrs={"administrative_id": sql_id})[:]
                _type = "village"
                for canton in liste_cantons:
                    [liste_villages.append(elt) for elt in get_administrative_levels_by_type(administrative_levels_db, _type.title(), attrs={"parent_id": canton['administrative_id']})[:]]
            
            if _type == "village":
                if not liste_villages:
                    liste_villages = get_administrative_levels_by_type(administrative_levels_db, _type.title(), attrs={"administrative_id": sql_id})[:]
        
            
            for _db in nsc.get_dbs():
                if "facilitator_" in _db:
                    facilitator_db = nsc.get_db(_db)
                    query_result = facilitator_db.get_query_result({"type": 'facilitator'})[:]
                    if query_result:
                        doc = query_result[0]
                        _village = None
                        for _village in doc['administrative_levels']:
                            for village in liste_villages:
                                if _village['id'] == village['administrative_id']: #_village['name'] == village['name'] and 
                                    for _task in facilitator_db.get_query_result({"type": 'task'})[:]:
                                        if not _task['completed']:
                                            nbr_tasks_completed += 1
                                        nbr_tasks += 1
                                    if _village and not _region:
                                        _region = get_region_of_village_by_sql_id(administrative_levels_db, _village['id']) 
                                        

            percentage_tasks_completed = ((nbr_tasks_completed/nbr_tasks)*100) if nbr_tasks else 0

        elif _type in ["phase", "activity", "task"]:
            if _type in ("phase", 'activity'):
                for _db in nsc.get_dbs():
                    if "facilitator_" in _db:
                        facilitator_db = nsc.get_db(_db)
                        query_result = facilitator_db.get_query_result({"type": _type, "sql_id": int(sql_id)})[:]
                        if query_result:
                            for _task in facilitator_db.get_query_result({"type": 'task', (str(type_header)+"_id"): query_result[0]['_id']})[:]:
                                if str(_task['administrative_level_id']).isdigit():
                                    _region = get_region_of_village_by_sql_id(administrative_levels_db, _task['administrative_level_id'])
                                    if _region:
                                        _region_name = _region['name']
                                        if regions.get(_region_name):
                                            if not _task['completed']:
                                                regions[_region_name]["nbr_tasks_completed"] += 1
                                            regions[_region_name]["nbr_tasks"] += 1
                            
            elif _type == "task":
                for _db in nsc.get_dbs():
                    facilitator_db = nsc.get_db(_db)
                    _tasks = facilitator_db.get_query_result({"type": 'task', "sql_id": sql_id})[:]
                    for _task in _tasks:
                        if str(_task['administrative_level_id']).isdigit():
                            _region = get_region_of_village_by_sql_id(administrative_levels_db, _task['administrative_level_id'])
                            if _region:
                                _region_name = _region['name']
                                if regions.get(_region_name):
                                    if not _task['completed']:
                                        regions[_region_name]["nbr_tasks_completed"] += 1
                                    regions[_region_name]["nbr_tasks"] += 1
                    

            for region, values in regions.items():
                regions[region]["percentage_tasks_completed"] = ((regions[region]["nbr_tasks_completed"]/regions[region]["nbr_tasks"])*100) if regions[region]["nbr_tasks"] else 0


        if search_by_locality:
            return self.render_to_json_response({
                "type": type_header.title(), 
                "nbr_tasks": nbr_tasks,
                "nbr_tasks_completed": nbr_tasks_completed,
                "percentage_tasks_completed": percentage_tasks_completed,
                "region": _region["name"] if _region else None,
                "search_by_locality": search_by_locality
            }, safe=False)
        
        return self.render_to_json_response({
            "type": type_header, 
            "regions": regions,
            "search_by_locality": search_by_locality
        }, safe=False)