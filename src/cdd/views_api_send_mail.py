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


def send_invalidation_reviewed_mail(request, task, facilitator, fields_updated, attachments_updated, no_sql_db_name):
    """Notifie le validateur (+ le facilitateur) qu'une tâche invalidée a été
    reprise. Extrait de `RestSendMail.post` pour être réutilisable tel quel
    par la sauvegarde web du menu "Tâches (cycle DCC)" (dashboard.task_cycle),
    qui appelle cette fonction directement (même process, pas d'aller-retour
    HTTP) au lieu de dupliquer cette logique. `task` doit porter `action_by`
    (posé par ValidateTaskView à l'invalidation) — appelant responsable de ne
    déclencher ceci QUE quand le doc était bien `validated is False`.

    Renvoie (ok: bool, message: str)."""
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
        )
        mail_message = _("Mail sent successfully")
    except Exception:
        pass
    if msg == 'error':
        return False, _("An error occurred while sending the email")
    return True, mail_message


class RestSendMail(APIView):
    throttle_classes = ()
    permission_classes = ()

    def post(self, request):
        ok, mail_message = send_invalidation_reviewed_mail(
            request,
            request.data['task'],
            request.data['facilitator'],
            request.data['fields_updated'],
            request.data['attachments_updated'],
            request.data['no_sql_db_name'],
        )
        return Response(
            {"message": mail_message, "ok": ok},
            status=status.HTTP_200_OK if ok else status.HTTP_400_BAD_REQUEST
        )
