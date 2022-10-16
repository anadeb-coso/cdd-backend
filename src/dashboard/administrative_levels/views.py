from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import generic

from dashboard.mixins import AJAXRequestMixin, JSONResponseMixin
from dashboard.utils import get_child_administrative_levels, get_parent_administrative_level
from no_sql_client import NoSQLClient


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
