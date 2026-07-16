from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.translation import gettext_lazy
from django.views import generic
from django.contrib.auth.models import User
import datetime

from dashboard.facilitators.forms import FilterFacilitatorForm
from dashboard.mixins import PageMixin
from administrativelevels.models import AdministrativeLevel, CVD
from dashboard.administrative_levels.functions import get_cascade_villages_by_administrative_level_id
from reports.models import VillageCommittee
from cdd.call_objects_from_other_db import mis_objects_call
from .forms import FilterTypeCommittesForm, COMMITTEE




class CommitteesListView(PageMixin, LoginRequiredMixin, generic.ListView):
    model = User
    queryset = []
    template_name = 'reports/reports/committees/index.html'
    context_object_name = 'committees'
    title = gettext_lazy('Committees')
    active_level1 = 'reports'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]

    def get_queryset(self):
        return super().get_queryset()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = FilterFacilitatorForm()
        context['type_committees_form'] = FilterTypeCommittesForm()
        context['breadcrumb'] = False

        return context
    


class CommitteesListTableView(LoginRequiredMixin, generic.ListView):
    template_name = 'reports/reports/committees/committees.html'
    context_object_name = 'committees_data'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        committees = len(self.request.GET.getlist('committees[]'))
        context['committees_is_list'] = committees >= 2 or committees == 0

        return context
    
    def get_results(self):
        id_region = self.request.GET.get('id_region')
        id_prefecture = self.request.GET.get('id_prefecture')
        id_commune = self.request.GET.get('id_commune')
        id_canton = self.request.GET.get('id_canton')
        id_village = self.request.GET.get('id_village')
        type_field = self.request.GET.get('type_field')
        committees_list = self.request.GET.getlist('committees[]')
        
        _id = 0
        
        committees = []

        def get_committees(liste_villages=None):

            queryset = VillageCommittee.objects.filter(project_name=self.request.session.get('project_name'))

            if committees_list:
                queryset = queryset.filter(name__in=committees_list)

            if liste_villages == None:
                return queryset
            elif liste_villages:
                return queryset.filter(cvd_id__in=liste_villages)
            
            return []
        
        if (id_region or id_prefecture or id_commune or id_canton or id_village) and type_field:
            _type = None
            if id_region and type_field == "region":
                _type = "region"
                _id = id_region
            elif id_prefecture and type_field == "prefecture":
                _type = "prefecture"
                _id = id_prefecture
            elif id_commune and type_field == "commune":
                _type = "commune"
                _id = id_commune
            elif id_canton and type_field == "canton":
                _type = "canton"
                _id = id_canton
            elif id_village and type_field == "village":
                _type = "village"
                _id = id_village
                
            
            if type(_id) is not list:
                liste_villages = get_cascade_villages_by_administrative_level_id(_id)
                
                if liste_villages:
                    cvds_ids = list(set(list(mis_objects_call.filter_objects(
                        CVD,
                        administrativelevel__in=list(set([v['id'] for v in liste_villages]))
                    ).values_list('id', flat=True))))

                    committees = get_committees(cvds_ids)
                
            else:
                committees = get_committees()
        else:
            committees = get_committees()

        if committees:
            committees = committees.values(
                "id", "name", "description", 
                "region", "prefecture", "commune", "canton", "cvd_name", 
                "meeting_date", "cvd_existence", "is_full_staff", "number_of_members", 
                "members_included_women", "members", "method_used_to_select_members"
            )

            dictinnary = {
                "president": "presidents", 

                "secretarieGeneral": "secretariegenerals", 

                "tresorierGeneral": "tresoriergenerals",

                "chefDeVillage": "chefdevillages",

                **dict((f"femmeLeader{i}", "femmeleaders") for i in range(1,8)),

                **dict((f"member_{i}", "representantsjeunes") for i in range(1,8)),
            }
            data = {
                "committees": [],
                "members": {
                    "presidents": [],
                    "secretariegenerals": [],
                    "tresoriergenerals": [],
                    "chefdevillages": [],
                    "femmeleaders": [],
                    "representantsjeunes": []
                }
            }
            # print(datetime.datetime.now())
            for committee in committees:
                
                _members = {
                    [k for k in list(dictinnary.keys()) if key.endswith(k)][0]: value
                    for key, value in committee.get('members', {}).items()
                    if any(k for k in list(dictinnary.keys()) if key.endswith(k))
                }
                
                for _member_k, _member_v in _members.items():
                    elt = {
                        "member": _member_v,
                        "locality": f"{committee['region']}, {committee['prefecture']}, {committee['commune']}, {committee['canton']}, {committee['cvd_name']}",
                        "method_used_to_select_members": committee['method_used_to_select_members'],
                        "description": committee['description']
                    }
                    if elt not in data['members'][dictinnary[_member_k]]:
                        data['members'][dictinnary[_member_k]].append(elt)

                data['committees'].append(
                    {'id' : f'committee-id-{committee["id"]}', 'object': committee}
                )
            
            # print(datetime.datetime.now())

            
        return data

    def get_queryset(self):
        return self.get_results()
    