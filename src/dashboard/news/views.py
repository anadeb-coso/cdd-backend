from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy
from django.views import generic
from news.models import News
from dashboard.facilitators.forms import FilterFacilitatorForm
from dashboard.mixins import PageMixin, AJAXRequestMixin

from .forms import FilterNewsFormMultiChoices
from dashboard.administrative_levels.functions import get_cascade_villages_by_administrative_level_id
from news.models import News
from .functions import chunk_list


class NewsListView(PageMixin, LoginRequiredMixin, generic.ListView):
    model = News
    queryset = []
    template_name = 'news/list.html'
    context_object_name = 'news'
    title = gettext_lazy('News')
    active_level1 = 'news'
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
        context['form'] = FilterNewsFormMultiChoices()
        context['breadcrumb'] = False
        context['all_total_news'] = News.objects.all().count()
        
            
        return context
    


class NewsListTableView(LoginRequiredMixin, generic.ListView):
    template_name = 'news/news_list.html'
    context_object_name = 'news'

    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        index = int(self.request.GET.get('index'))
        offset = int(self.request.GET.get('offset'))
        news = self.get_results()
        context['total_news'] = news.count()

        context['news'] = chunk_list(news[index:index + offset], 4)
        
        return context
        

    def _get_ids_list(self, elt: str):
        if type(elt) is str:
            return [_elt for _elt in elt.split(',') if _elt]
        return []
    

    def get_results(self):
        id_categories = self.request.GET.getlist('id_categories[]')
        id_tags = self.request.GET.getlist('id_tags[]')
        
        ids_region = self.request.GET.getlist('id_regions[]')
        ids_prefecture = self.request.GET.getlist('id_prefectures[]')
        ids_commune = self.request.GET.getlist('id_communes[]')
        ids_canton = self.request.GET.getlist('id_cantons[]')
        ids_village = self.request.GET.getlist('id_villages[]')
        type_field = self.request.GET.get('type_field')
        print(type_field)
        _ids = []
        _type = "All"
        news = []
        if (ids_region or ids_prefecture or ids_commune or ids_canton or ids_village) and type_field:
            if ids_village:
                _type = "village"
                _ids = ids_village
            elif ids_canton:
                _type = "canton"
                _ids = ids_canton
            elif ids_commune:
                _type = "commune"
                _ids = ids_commune
            elif ids_prefecture:
                _type = "prefecture"
                _ids = ids_prefecture
            elif ids_region:
                _type = "region"
                _ids = ids_region
            
            print(_ids)
            liste_villages = get_cascade_villages_by_administrative_level_id(_ids)
            
            news = News.objects.filter(
                administrative_levels__name=[{
                    "name": v['name'], 
                    "id": v['id'], 
                    "parent": v['parent'], 
                    "type": v['type'] 
                } for v in liste_villages]
            )
        else:
            news = News.objects.all()
            
        if id_categories:
            news = news.filter(category__id__in=[int(cId) for cId in id_categories if cId not in ('', 'null', 'None')])
            
        if id_tags:
            news = news.filter(tags__id__in=[int(cId) for cId in id_tags if cId not in ('', 'null', 'None')])
            
        return news

    def get_queryset(self):

        return []
    


class NewsDetailView(PageMixin, LoginRequiredMixin, generic.DetailView):
    template_name = 'news/detail.html'
    context_object_name = 'new'
    title = gettext_lazy('Detail')
    active_level1 = 'news'
    model = News
    breadcrumb = [
        {
            'url': reverse_lazy('dashboard:news:list'),
            'title': gettext_lazy('News')
        },
        {
            'url': '',
            'title': title
        }
    ]