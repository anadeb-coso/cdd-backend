from rest_framework.views import APIView
from rest_framework import status
from rest_framework.response import Response
from django.utils.translation import gettext_lazy as _
from django.urls import reverse_lazy
from django.contrib.auth.models import User
from datetime import datetime


from cdd.utils import get_administrative_region_name
from cdd.my_librairies.mail.send_mail import send_email
from dashboard.templatetags.custom_tags import get_group_high
import locale


class RestSendMail(APIView):
    throttle_classes = ()
    permission_classes = ()

    def post(self, request):

        task = request.data['task']
        facilitator = request.data['facilitator']
        fields_updated = request.data['fields_updated']
        attachments_updated = request.data['attachments_updated']
        no_sql_db_name = request.data['no_sql_db_name']
        # print(fields_updated)
        # print(attachments_updated)

        subject = f'[COSO Apps : {datetime.now().strftime("%Y-%m-%d")}] {_("Invalidated task reviewed by the Facilitator")} : {task.get("name")}'
        administrative_region_name = get_administrative_region_name(task.get("administrative_level_id"))
        
        msg = 'error'
        try:
            locale.setlocale(locale.LC_TIME, 'fr_FR.UTF-8')
            msg = send_email(
                subject,
                "mail/send/comment",
                {
                    "datas": {
                        _("Title"): _("Invalidated task reviewed by the Facilitator"), 
                        _("Phase"): task.get("phase_name"),
                        _("Activity"): task.get("activity_name"),
                        _("Task"): task.get("name"),
                        _("Location Name"): administrative_region_name,
                        _("Modified variable(s)"): fields_updated + attachments_updated,
                        _("Date"): task['last_updated'],
                    },
                    "user": {
                        _("Facilitator Name"): facilitator.get('name'),
                        _("Facilitator Phone"): facilitator.get('phone'),
                        _("Facilitator Sex"): "F" if facilitator.get('sex') == "Mme" else "M",
                        _("Validator"): f"{task['action_by']['user_last_name']} {task['action_by']['user_first_name']}",
                        _("Validator Type"): get_group_high(User.objects.filter(email=task['action_by']['user_email']).first()),
                        _("Validator Email"): task['action_by']['user_email'],
                    },
                    "url": f"{request.scheme}://{request.META['HTTP_HOST']}{reverse_lazy('dashboard:facilitators:detail', args=[no_sql_db_name])}"
                },
                [facilitator.get('email'), task['action_by']['user_email']],
                project_name=task.get("project_name", "COSO")
                # ["adaboubvincent@gmail.com"],
                # ["adaboubvincent@gmail.com"]
            )
            mail_message = _("Mail sent successfully")
        except Exception as exc:
            pass
        if msg == 'error':
            mail_message = _("An error occurred while sending the email")
            return Response(
                {
                    "message": mail_message,
                    "ok": False
                }, 
                status=status.HTTP_400_BAD_REQUEST
            )
            

        return Response(
            {
                "message": mail_message,
                "ok": True
            }, 
            status=status.HTTP_200_OK
        )
