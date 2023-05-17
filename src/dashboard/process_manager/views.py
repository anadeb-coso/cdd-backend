from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import generic
from django.db.models import Q
from datetime import datetime
from django.utils.translation import gettext_lazy

from dashboard.mixins import AJAXRequestMixin, JSONResponseMixin
from no_sql_client import NoSQLClient
from process_manager.models import Task, Phase, Activity
from .functions import get_cascade_phase_activity_task_by_their_id

class GetChoicesForNextPhaseActivitiesTasksView(AJAXRequestMixin, LoginRequiredMixin, JSONResponseMixin, generic.View):
    def get(self, request, *args, **kwargs):
        phase_name = request.GET.get('phase_name', None)
        activity_name = request.GET.get('activity_name', None)
        task_name = request.GET.get('task_name', None)
        _by_id = request.GET.get('by_id', None)
        phase_id = 0
        activity_id = 0
        
        if _by_id:
            if phase_name:
                phase_id = int(phase_name)
            if activity_name:
                activity_id = int(activity_name)
        
        if activity_name and phase_name:
            phase = Phase.objects.get(Q(name=phase_name) | Q(id=phase_id))
            activity = Activity.objects.get(Q(name=activity_name) | Q(id=activity_id))
            phases = Phase.objects.all().order_by("order")
            activies = phase.activity_set.get_queryset().order_by("phase__order", "order")
            tasks = activity.task_set.get_queryset().order_by("phase__order", "activity__order", "order")
        elif phase_name:
            phase = Phase.objects.get(Q(name=phase_name) | Q(id=phase_id))
            phases = Phase.objects.all().order_by("order")
            activies = phase.activity_set.get_queryset().order_by("phase__order", "order")
            tasks = phase.task_set.get_queryset().order_by("phase__order", "activity__order", "order")
        elif activity_name:
            activity = Activity.objects.get(Q(name=activity_name) | Q(id=activity_id))
            phases = Phase.objects.all().order_by("order")
            activies = Activity.objects.all().order_by("phase__order", "order")
            tasks = activity.task_set.get_queryset().order_by("phase__order", "activity__order", "order")
        else:
            phases = Phase.objects.all().order_by("order")
            activies = Activity.objects.all().order_by("phase__order", "order")
            tasks = Task.objects.all().order_by("phase__order", "activity__order", "order")

        datas = {'phases': [], 'activities': [], 'tasks': []}

        if _by_id:
            for p in phases:
                datas['phases'].append((p.id, p.name))
            
            for a in activies:
                datas['activities'].append((a.id, a.name))
            
            for t in tasks:
                datas['tasks'].append((t.id, t.name))
        else:
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

        # nsc = NoSQLClient()
        
        
        # if activity_id and phase_id:
        #     phase = Phase.objects.get(id=phase_id)
        #     activity = Activity.objects.get(id=activity_id)
        #     phases = Phase.objects.all().order_by("order")
        #     activies = phase.activity_set.get_queryset().order_by("phase__order", "order")
        #     tasks = activity.task_set.get_queryset().order_by("phase__order", "activity__order", "order")
        # elif phase_id:
        #     phase = Phase.objects.get(id=phase_id)
        #     phases = Phase.objects.all().order_by("order")
        #     activies = phase.activity_set.get_queryset().order_by("phase__order", "order")
        #     tasks = phase.task_set.get_queryset().order_by("phase__order", "activity__order", "order")
        # elif activity_id:
        #     activity = Activity.objects.get(id=activity_id)
        #     phases = Phase.objects.all().order_by("order")
        #     activies = Activity.objects.all().order_by("phase__order", "order")
        #     tasks = activity.task_set.get_queryset().order_by("phase__order", "activity__order", "order")
        # else:
        #     phases = Phase.objects.all().order_by("order")
        #     activies = Activity.objects.all().order_by("phase__order", "order")
        #     tasks = Task.objects.all().order_by("phase__order", "activity__order", "order")

        # datas = {'phases': [], 'activities': [], 'tasks': []}

        # for p in phases:
        #     datas['phases'].append((p.id, p.name))
        
        # for a in activies:
        #     datas['activities'].append((a.id, a.name))
        
        # for t in tasks:
        #     datas['tasks'].append((t.id, t.name))

        # return self.render_to_json_response(datas, safe=False)

        return self.render_to_json_response(
            get_cascade_phase_activity_task_by_their_id(phase_id, activity_id, task_id), 
            safe=False
        )


class ValidateTaskView(AJAXRequestMixin, LoginRequiredMixin, JSONResponseMixin, generic.View):
    def get(self, request, *args, **kwargs):
        no_sql_db_name = request.GET.get('no_sql_db_name')
        task_id = request.GET.get('task_id')
        action_code = int(request.GET.get('action_code') if request.GET.get('action_code') else 0)
        message = None
        status = "ok"
        try:
            nsc = NoSQLClient()
            db = nsc.get_db(no_sql_db_name)
            task = db[db.get_query_result({"type": "task", "_id": task_id})[:][0]['_id']]

            datetime_now = datetime.now()
            date_validated = f"{str(datetime_now.year)}-{str(datetime_now.month)}-{str(datetime_now.day)} {str(datetime_now.hour)}:{str(datetime_now.minute)}:{str(datetime_now.second)}"

            #Get the info of the User who's validate the task
            actions_by = task.get('actions_by') if task.get('actions_by') else []
            action_by = {
                'type': ("Validated" if bool(action_code) else "Invalidated"), 
                'user_name': request.user.username, 'user_id': request.user.id,
                'user_last_name': request.user.last_name, 'user_first_name': request.user.first_name,
                'user_email': request.user.email, 'action_date': date_validated
            }
            actions_by.append(action_by)
            #End

            nsc.update_doc_uncontrolled(db, task['_id'], {
                "validated": bool(action_code),
                "date_validated": date_validated if bool(action_code) else None,
                "action_by": action_by,
                "actions_by": actions_by
                }
            )
            message = gettext_lazy("Task validated").__str__() if bool(action_code) else gettext_lazy("Task not validated").__str__()
        except Exception as exc:
            message = gettext_lazy("An error has occurred...").__str__()
            status = "error"

        return self.render_to_json_response({"message": message, "status": status}, safe=False)
