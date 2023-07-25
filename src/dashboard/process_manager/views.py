from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import generic
from django.db.models import Q
from datetime import datetime
from django.utils.translation import gettext_lazy
from django.urls import reverse_lazy
from django.conf import settings

from dashboard.mixins import AJAXRequestMixin, JSONResponseMixin
from no_sql_client import NoSQLClient
from process_manager.models import Task, Phase, Activity
from .functions import get_cascade_phase_activity_task_by_their_id
from cdd.my_librairies.mail.send_mail import send_email
from cdd.my_librairies.sms.send_sms import send_sms
from cdd.utils import get_administrative_region_name

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
        in_validation_comment = request.GET.get('in_validation_comment')
        action_code = int(request.GET.get('action_code') if request.GET.get('action_code') else 0)
        message = None
        status = "ok"
        mail_message, sms_message = None, None
        try:
            nsc = NoSQLClient()
            db = nsc.get_db(no_sql_db_name)
            task = db[db.get_query_result({"type": "task", "_id": task_id})[:][0]['_id']]
            if task.get('completed'):
                datetime_now = datetime.now()
                date_validated = f"{str(datetime_now.year)}-{str(datetime_now.month)}-{str(datetime_now.day)} {str(datetime_now.hour)}:{str(datetime_now.minute)}:{str(datetime_now.second)}"

                #Get the info of the User who's validate the task
                actions_by = task.get('actions_by') if task.get('actions_by') else []
                action_by = {
                    'type': ("Validated" if bool(action_code) else "Invalidated"), 
                    'user_name': request.user.username, 'user_id': request.user.id,
                    'user_last_name': request.user.last_name, 'user_first_name': request.user.first_name,
                    'user_email': request.user.email, 'action_date': date_validated,
                    'comment': in_validation_comment
                }
                actions_by.insert(0, action_by)
                #End

                nsc.update_doc_uncontrolled(db, task['_id'], {
                    "validated": bool(action_code),
                    "date_validated": date_validated if bool(action_code) else None,
                    "action_by": action_by,
                    "actions_by": actions_by
                    }
                )

                #Send Mail - SMS
                if not bool(action_code):
                    facilitator = db[db.get_query_result({"type": "facilitator"})[:][0]['_id']]
                    subject = f'{gettext_lazy("Task Invalided")} : {task.get("name")}'
                    administrative_region_name = get_administrative_region_name(task.get("administrative_level_id"))
                    
                    try:
                        msg = send_email(
                            subject,
                            "mail/send/comment",
                            {
                                "datas": {
                                    gettext_lazy("Title"): gettext_lazy("Task Invalided"), 
                                    gettext_lazy("Comment"): in_validation_comment,
                                    gettext_lazy("Phase"): task.get("phase_name"),
                                    gettext_lazy("Activity"): task.get("activity_name"),
                                    gettext_lazy("Task"): task.get("name"),
                                    gettext_lazy("Location Name"): administrative_region_name,
                                    gettext_lazy("Date"): date_validated,
                                },
                                "user": {
                                    gettext_lazy("Facilitator Name"): facilitator.get('name'),
                                    gettext_lazy("Phone"): facilitator.get('phone'),
                                    gettext_lazy("Sex"): facilitator.get('sex'),
                                },
                                "url": f"{request.scheme}://{request.META['HTTP_HOST']}{reverse_lazy('dashboard:facilitators:detail', args=[no_sql_db_name])}"
                            },
                            [facilitator.get('email')]
                        )
                        mail_message = gettext_lazy("Mail sent successfully")
                    except:
                        mail_message = gettext_lazy("An error occurred while sending the email")

                    try:
                        TWILIO_REGION = str(settings.TWILIO_REGION)
                        send_sms(
                            f"+{(facilitator.get('phone') if (facilitator.get('phone') and TWILIO_REGION in facilitator.get('phone') and TWILIO_REGION == facilitator.get('phone')[0:len(TWILIO_REGION)]) else (TWILIO_REGION+facilitator.get('phone')))}", 
                            body=f'{subject}\n\
                                {gettext_lazy("Comment")}: {in_validation_comment}\n\
                                {gettext_lazy("Phase")}: {task.get("phase_name")}\n\
                                {gettext_lazy("Activity")}: {task.get("activity_name")}\n\
                                {gettext_lazy("Task")}: {task.get("name")}\n\
                                {gettext_lazy("Location Name")}: {administrative_region_name}\n\
                                {gettext_lazy("Date")}: {date_validated}\n\
                            '
                        )
                        sms_message = gettext_lazy("SMS sent successfully")
                    except Exception as exc:
                        print(exc)
                        sms_message = gettext_lazy("An error occurred while sending the sms")
                #End Send Mail - SMS


                message = gettext_lazy("Task validated").__str__() if bool(action_code) else gettext_lazy("Task not validated").__str__()
            else:
                message = gettext_lazy("The task isn't completed").__str__()
                status = "error"
        except Exception as exc:
            message = gettext_lazy("An error has occurred...").__str__()
            status = "error"

        return self.render_to_json_response(
            {
                "message": message, "status": status, 
                "sms_message": sms_message, "mail_message": mail_message
            }, safe=False
        )


class CompleteTaskView(AJAXRequestMixin, LoginRequiredMixin, JSONResponseMixin, generic.View):
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
            date_completed = f"{str(datetime_now.year)}-{str(datetime_now.month)}-{str(datetime_now.day)} {str(datetime_now.hour)}:{str(datetime_now.minute)}:{str(datetime_now.second)}"

            #Get the info of the User who's complete the task
            actions_by = task.get('actions_by') if task.get('actions_by') else []
            action_complete_by = {
                'type': ("Completed" if bool(action_code) else "Uncompleted"), 
                'user_name': request.user.username, 'user_id': request.user.id,
                'user_last_name': request.user.last_name, 'user_first_name': request.user.first_name,
                'user_email': request.user.email, 'action_date': date_completed
            }
            actions_by.append(action_complete_by)
            #End

            nsc.update_doc_uncontrolled(db, task['_id'], {
                "completed": bool(action_code),
                "date_action_complete_by": date_completed if bool(action_code) else None,
                "action_complete_by": action_complete_by,
                "actions_by": actions_by
                }
            )
            message = gettext_lazy("Task completed").__str__() if bool(action_code) else gettext_lazy("Task not completed").__str__()
        except Exception as exc:
            message = gettext_lazy("An error has occurred...").__str__()
            status = "error"

        return self.render_to_json_response({"message": message, "status": status}, safe=False)