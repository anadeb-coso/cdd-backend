from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import generic

from dashboard.mixins import AJAXRequestMixin, JSONResponseMixin
from dashboard.utils import get_child_administrative_levels, get_parent_administrative_level
from no_sql_client import NoSQLClient
from administrativelevels import models as administrativelevels_models
from .functions import get_administrative_levels_under_json

class GetChoicesForNextAdministrativeLevelView(AJAXRequestMixin, LoginRequiredMixin, JSONResponseMixin, generic.View):
    def get(self, request, *args, **kwargs):
        parent_id = request.GET.get('parent_id')
        exclude_lower_level = request.GET.get('exclude_lower_level', None)

        nsc = NoSQLClient()
        administrative_levels_db = nsc.get_db("administrative_levels")
        data = get_child_administrative_levels(administrative_levels_db, parent_id)

        if data and exclude_lower_level and not get_child_administrative_levels(
                administrative_levels_db, data[0]['administrative_id']):
            data = []

        return self.render_to_json_response(data, safe=False)


class GetAncestorAdministrativeLevelsView(AJAXRequestMixin, LoginRequiredMixin, JSONResponseMixin, generic.View):
    def get(self, request, *args, **kwargs):
        administrative_id = request.GET.get('administrative_id', None)
        ancestors = []
        if administrative_id:
            nsc = NoSQLClient()
            administrative_levels_db = nsc.get_db("administrative_levels")
            has_parent = True
            while has_parent:
                parent = get_parent_administrative_level(administrative_levels_db, administrative_id)
                if parent:
                    administrative_id = parent['administrative_id']
                    ancestors.insert(0, administrative_id)
                else:
                    has_parent = False

        return self.render_to_json_response(ancestors, safe=False)


class GetChoicesForNextAdministrativeLevelAllView(AJAXRequestMixin, LoginRequiredMixin, JSONResponseMixin, generic.View):
    def get(self, request, *args, **kwargs):
        # parent_id = request.GET.get('parent_id')

        # nsc = NoSQLClient()
        # administrative_levels_db = nsc.get_db("administrative_levels")
        # data = get_child_administrative_levels(administrative_levels_db, parent_id)

        # parent_name = None
        # ad = data[0] if data else None
        # if ad:
        #     if ad.get('administrative_level') == 'Prefecture':
        #         parent_name = "region"
        #     elif ad.get('administrative_level') == 'Commune':
        #         parent_name = "prefecture"
        #     elif ad.get('administrative_level') == 'Canton':
        #         parent_name = "commune"
        #     elif ad.get('administrative_level') == 'Village':
        #         parent_name = "canton"

        # # if parent_name == "region":
        # datas = {
        #     "prefectures": data if parent_name == "region" else [], 
        #     "communes": data if parent_name == "prefecture" else [], 
        #     "cantons": data if parent_name == "commune" else [], 
        #     "villages": data if parent_name == "canton" else []
        # }
        # for p in datas["prefectures"]:
        #     [datas["communes"].append(o) for o in get_child_administrative_levels(administrative_levels_db, p.get("administrative_id"))]

        # for c in datas["communes"]:
        #     [datas["cantons"].append(o) for o in get_child_administrative_levels(administrative_levels_db, c.get("administrative_id"))]
        
        # for c in datas["cantons"]:
        #     [datas["villages"].append(o) for o in get_child_administrative_levels(administrative_levels_db, c.get("administrative_id"))]


        datas = {}

        _id = request.GET.get('parent_id')
        if _id:
            ad_obj = administrativelevels_models.AdministrativeLevel.objects.using('mis').get(id=int(_id))

            ads = ad_obj.administrativelevel_set.get_queryset()
            _type = ad_obj.type
            datas = {
                "prefectures": ads if _type == "Region" else [], 
                "communes": ads if _type == "Prefecture" else [], 
                "cantons": ads if _type == "Commune" else [], 
                "villages": ads if _type == "Canton" else []
            }
            for p in datas["prefectures"]:
                [datas["communes"].append(o) for o in p.administrativelevel_set.get_queryset()]

            for c in datas["communes"]:
                [datas["cantons"].append(o) for o in c.administrativelevel_set.get_queryset()]
            
            for c in datas["cantons"]:
                [datas["villages"].append(o) for o in c.administrativelevel_set.get_queryset()]

            datas["prefectures"] = get_administrative_levels_under_json(datas["prefectures"])
            datas["communes"] = get_administrative_levels_under_json(datas["communes"])
            datas["cantons"] = get_administrative_levels_under_json(datas["cantons"])
            datas["villages"] = get_administrative_levels_under_json(datas["villages"])

            return self.render_to_json_response(datas, safe=False)
    
        return self.render_to_json_response(datas, safe=False)