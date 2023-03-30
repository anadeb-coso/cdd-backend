from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import generic

from dashboard.mixins import AJAXRequestMixin, JSONResponseMixin
from no_sql_client import NoSQLClient
from process_manager.models import Task, Phase, Activity


class GetChoicesForNextPhaseActivitiesTasksView(AJAXRequestMixin, LoginRequiredMixin, JSONResponseMixin, generic.View):
    def get(self, request, *args, **kwargs):
        phase_name = request.GET.get('phase_name', None)
        activity_name = request.GET.get('activity_name', None)
        task_name = request.GET.get('task_name', None)

        nsc = NoSQLClient()
        
        
        if activity_name and phase_name:
            phase = Phase.objects.get(name=phase_name)
            activity = Activity.objects.get(name=activity_name)
            phases = Phase.objects.all().order_by("order")
            activies = phase.activity_set.get_queryset().order_by("phase__order", "order")
            tasks = activity.task_set.get_queryset().order_by("phase__order", "activity__order", "order")
        elif phase_name:
            phase = Phase.objects.get(name=phase_name)
            phases = Phase.objects.all().order_by("order")
            activies = phase.activity_set.get_queryset().order_by("phase__order", "order")
            tasks = phase.task_set.get_queryset().order_by("phase__order", "activity__order", "order")
        elif activity_name:
            activity = Activity.objects.get(name=activity_name)
            phases = Phase.objects.all().order_by("order")
            activies = Activity.objects.all().order_by("phase__order", "order")
            tasks = activity.task_set.get_queryset().order_by("phase__order", "activity__order", "order")
        else:
            phases = Phase.objects.all().order_by("order")
            activies = Activity.objects.all().order_by("phase__order", "order")
            tasks = Task.objects.all().order_by("phase__order", "activity__order", "order")

        datas = {'phases': [], 'activities': [], 'tasks': []}

        for p in phases:
            datas['phases'].append((p.name, p.name))
        
        for a in activies:
            datas['activities'].append((a.name, a.name))
        
        for t in tasks:
            datas['tasks'].append((t.name, t.name))

        return self.render_to_json_response(datas, safe=False)



class GetChoicesForNextPhaseActivitiesTasksByIdView(AJAXRequestMixin, LoginRequiredMixin, JSONResponseMixin, generic.View):
    def get(self, request, *args, **kwargs):
        phase_id = int(request.GET.get('phase_name') if request.GET.get('phase_name') else 0)
        activity_id = int(request.GET.get('activity_name') if request.GET.get('activity_name') else 0)
        task_id = int(request.GET.get('task_name') if request.GET.get('task_name') else 0)

        nsc = NoSQLClient()
        
        
        if activity_id and phase_id:
            phase = Phase.objects.get(id=phase_id)
            activity = Activity.objects.get(id=activity_id)
            phases = Phase.objects.all().order_by("order")
            activies = phase.activity_set.get_queryset().order_by("phase__order", "order")
            tasks = activity.task_set.get_queryset().order_by("phase__order", "activity__order", "order")
        elif phase_id:
            phase = Phase.objects.get(id=phase_id)
            phases = Phase.objects.all().order_by("order")
            activies = phase.activity_set.get_queryset().order_by("phase__order", "order")
            tasks = phase.task_set.get_queryset().order_by("phase__order", "activity__order", "order")
        elif activity_id:
            activity = Activity.objects.get(id=activity_id)
            phases = Phase.objects.all().order_by("order")
            activies = Activity.objects.all().order_by("phase__order", "order")
            tasks = activity.task_set.get_queryset().order_by("phase__order", "activity__order", "order")
        else:
            phases = Phase.objects.all().order_by("order")
            activies = Activity.objects.all().order_by("phase__order", "order")
            tasks = Task.objects.all().order_by("phase__order", "activity__order", "order")

        datas = {'phases': [], 'activities': [], 'tasks': []}

        for p in phases:
            datas['phases'].append((p.id, p.name))
        
        for a in activies:
            datas['activities'].append((a.id, a.name))
        
        for t in tasks:
            datas['tasks'].append((t.id, t.name))

        return self.render_to_json_response(datas, safe=False)
