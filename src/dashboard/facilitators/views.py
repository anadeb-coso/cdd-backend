from django.contrib.auth.hashers import make_password
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import redirect
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy
from django.views import generic

from authentication.models import Facilitator
from dashboard.facilitators.forms import FacilitatorForm, FilterTaskForm, UpdateFacilitatorForm
from dashboard.mixins import AJAXRequestMixin, PageMixin
from no_sql_client import NoSQLClient


class FacilitatorListView(PageMixin, LoginRequiredMixin, generic.ListView):
    model = Facilitator
    queryset = Facilitator.objects.all()
    template_name = 'facilitators/list.html'
    context_object_name = 'facilitators'
    title = gettext_lazy('Facilitators')
    active_level1 = 'facilitators'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]

    def get_queryset(self):
        return super().get_queryset()


class FacilitatorMixin:
    doc = None
    obj = None
    facilitator_db = None
    facilitator_db_name = None

    def dispatch(self, request, *args, **kwargs):
        nsc = NoSQLClient()
        try:
            self.facilitator_db_name = kwargs['id']
            self.facilitator_db = nsc.get_db(self.facilitator_db_name)
            query_result = self.facilitator_db.get_query_result({"type": 'facilitator'})[:]
            self.doc = self.facilitator_db[query_result[0]['_id']]
            self.obj = get_object_or_404(Facilitator, no_sql_db_name=kwargs['id'])
        except Exception:
            raise Http404
        return super().dispatch(request, *args, **kwargs)


class FacilitatorDetailView(FacilitatorMixin, PageMixin, LoginRequiredMixin, generic.DetailView):
    template_name = 'facilitators/profile.html'
    context_object_name = 'facilitator_doc'
    title = gettext_lazy('Facilitator Profile')
    active_level1 = 'facilitators'
    model = Facilitator
    breadcrumb = [
        {
            'url': reverse_lazy('dashboard:facilitators:list'),
            'title': gettext_lazy('Facilitators')
        },
        {
            'url': '',
            'title': title
        }
    ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['facilitator'] = self.obj
        context['form'] = FilterTaskForm(initial={'facilitator_db_name': self.facilitator_db_name})
        tasks = self.facilitator_db.get_query_result({"type": "task"})
        total_tasks = 0
        for _ in tasks:
            total_tasks += 1
        context['total_tasks'] = total_tasks
        return context

    def get_object(self, queryset=None):
        return self.doc


class FacilitatorTaskListView(FacilitatorMixin, AJAXRequestMixin, LoginRequiredMixin, generic.ListView):
    template_name = 'facilitators/task_list.html'
    context_object_name = 'tasks'

    def get_queryset(self):
        index = int(self.request.GET.get('index'))
        offset = int(self.request.GET.get('offset'))
        administrative_level_id = self.request.GET.get('administrative_level')
        phase_id = self.request.GET.get('phase')
        activity_id = self.request.GET.get('activity')

        selector = {
            "type": "task"
        }

        if administrative_level_id:
            selector["administrative_level_id"] = administrative_level_id
        if phase_id:
            selector["phase_id"] = phase_id
        if activity_id:
            selector["activity_id"] = activity_id
        return self.facilitator_db.get_query_result(selector)[index:index + offset]


class CreateFacilitatorFormView(PageMixin, generic.FormView):
    template_name = 'facilitators/create.html'
    title = gettext_lazy('Create Facilitator')
    active_level1 = 'facilitators'
    form_class = FacilitatorForm
    success_url = reverse_lazy('dashboard:facilitators:list')
    breadcrumb = [
        {
            'url': reverse_lazy('dashboard:facilitators:list'),
            'title': gettext_lazy('Facilitators')
        },
        {
            'url': '',
            'title': title
        }
    ]

    def form_valid(self, form):
        data = form.cleaned_data
        password = make_password(data['password1'], salt=None, hasher='default')
        facilitator = Facilitator(username=data['username'], password=password, active=True)
        facilitator.save(replicate_design=False)
        doc = {
            "name": data['name'],
            "email": data['email'],
            "phone": data['phone'],
            "administrative_levels": data['administrative_levels'],
            "type": "facilitator"
        }
        nsc = NoSQLClient()
        facilitator_database = nsc.get_db(facilitator.no_sql_db_name)
        nsc.create_document(facilitator_database, doc)
        return super().form_valid(form)




class UpdateFacilitatorView(PageMixin, LoginRequiredMixin, generic.UpdateView):
    model = Facilitator
    template_name = 'facilitators/update.html'
    title = gettext_lazy('Edit Facilitator')
    active_level1 = 'facilitators'
    form_class = UpdateFacilitatorForm
    # success_url = reverse_lazy('dashboard:facilitators:list')
    breadcrumb = [
        {
            'url': reverse_lazy('dashboard:facilitators:list'),
            'title': gettext_lazy('Facilitators')
        },
        {
            'url': '',
            'title': title
        }
    ]
    
    facilitator_db = None
    facilitator = None
    doc = None
    facilitator_db_name = None

    def dispatch(self, request, *args, **kwargs):
        nsc = NoSQLClient()
        # try:
        self.facilitator = self.get_object()
        self.facilitator_db_name = self.facilitator.no_sql_db_name
        self.facilitator_db = nsc.get_db(self.facilitator_db_name)
        query_result = self.facilitator_db.get_query_result({"type": "facilitator", "name": self.facilitator.username})[:]
        self.doc = self.facilitator_db[query_result[0]['_id']]
        # self.obj = get_object_or_404(Facilitator, no_sql_db_name=kwargs['id'])
        # except Exception:
        #     raise Http404
        return super().dispatch(request, *args, **kwargs)



    def get_context_data(self, **kwargs):
        ctx = super(UpdateFacilitatorView, self).get_context_data(**kwargs)
        form = ctx.get('form')
        
        if self.doc:
            if form:
                for label, field in form.fields.items():
                    try:
                        form.fields[label].value = self.doc[label]
                    except Exception as exc:
                        pass
                    
                ctx.setdefault('form', form)
            ctx.setdefault('facilitator_administrative_levels', self.doc["administrative_levels"])

        return ctx

    def post(self, request, *args, **kwargs):
        
        if not self.facilitator_db_name:
            raise Http404("We don't find the database name for the facilitators.")

        form = UpdateFacilitatorForm(request.POST, instance=self.facilitator)
        if form.is_valid():
            return self.form_valid(form)
        return self.get(request, *args, **kwargs)

    def form_valid(self, form):
        data = form.cleaned_data
        facilitator = form.save(commit=False)
        facilitator = facilitator.simple_save()

        _administrative_levels = []
        for elt in data['administrative_levels']:
            exists = False
            for _elt in _administrative_levels:
                if _elt.get('id') == elt.get('id'):
                    exists = True
            if not exists:
                _administrative_levels.append(elt)

        doc = {
            "phone": data['phone'],
            "administrative_levels": _administrative_levels
        }
        nsc = NoSQLClient()
        nsc.update_doc(self.facilitator_db, self.doc['_id'], doc)
        return redirect('dashboard:facilitators:list')