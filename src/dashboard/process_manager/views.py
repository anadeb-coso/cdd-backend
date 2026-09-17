from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.views import generic
from django.db.models import Q
from datetime import datetime
from django.utils.translation import gettext_lazy
from django.urls import reverse_lazy
from django.conf import settings
from django.shortcuts import resolve_url
from django.http import HttpResponseRedirect
from django.contrib import messages
import itertools
import logging

logger = logging.getLogger(__name__)

from dashboard.mixins import AJAXRequestMixin, JSONResponseMixin, PageMixin
from no_sql_client import NoSQLClient
import grm_client
from process_manager.models import Task, Phase, Activity, Project, Cycle
from .functions import get_cascade_phase_activity_task_by_their_id
from cdd.my_librairies.mail.send_mail import send_email
from cdd.my_librairies.sms.send_sms import send_sms
from cdd.utils import get_administrative_region_name
from dashboard.templatetags.custom_tags import get_group_high
from assignments.models import AssignAdministrativeLevelToFacilitator
from cdd.call_objects_from_other_db import mis_objects_call
from authentication.models import Facilitator
from subprojects.models import Project as MisProject
from dashboard.facilitators.functions import (
    get_db_task, get_search_for_stabilized_facilitator_dbs
)
from subprojects.models import Project as ProjectMis, Cycle as CycleMis


def _get_on_list(_ids):
    if not _ids:
        return []
    if type(_ids) is not list:
        _ids = [_ids]
    return [_ for _ in _ids if _ not in ('', ' ', None)]

class GetChoicesForNextPhaseActivitiesTasksView(AJAXRequestMixin, LoginRequiredMixin, JSONResponseMixin, generic.View):
    def get(self, request, *args, **kwargs):
        phases_id = _get_on_list(self.request.GET.getlist('phase_name[]'))
        activities_id = _get_on_list(self.request.GET.getlist('activity_name[]'))
        tasks_id = _get_on_list(self.request.GET.getlist('task_name[]'))


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
                
        if (activity_name and phase_name) or (phases_id and activities_id):
            _phases = Phase.objects.filter(Q(name=phase_name) | Q(id=phase_id) | Q(id__in=phases_id), project_id=self.request.session.get('project_id'))
            _activities = Activity.objects.filter(Q(name=activity_name) | Q(id=activity_id) | Q(id__in=activities_id), project_id=self.request.session.get('project_id'))
            phases = Phase.objects.get_objects_by_general_filtre(request=self.request, attrs=None).order_by("order")
            activities = [elem for sous_liste in [_phase.activity_set.get_queryset().order_by("phase__order", "order") for _phase in _phases] for elem in sous_liste]
            tasks = [elem for sous_liste in [_activity.task_set.get_queryset().order_by("phase__order", "activity__order", "order") for _activity in _activities] for elem in sous_liste]
    
        elif phase_name or phase_id or phases_id:
            _phases = Phase.objects.filter(Q(name=phase_name) | Q(id=phase_id) | Q(id__in=phases_id), project_id=self.request.session.get('project_id'))
            phases = Phase.objects.get_objects_by_general_filtre(request=self.request, attrs=None).order_by("order")
            activities = [elem for sous_liste in [_phase.activity_set.get_queryset().order_by("phase__order", "order") for _phase in _phases] for elem in sous_liste]
            tasks = [elem for sous_liste in [_phase.task_set.get_queryset().order_by("phase__order", "activity__order", "order") for _phase in _phases] for elem in sous_liste]
        
        elif activity_name or activity_id or activities_id:
            _activities = Activity.objects.filter(Q(name=activity_name) | Q(id=activity_id) | Q(id__in=activities_id), project_id=self.request.session.get('project_id'))
            phases = Phase.objects.get_objects_by_general_filtre(request=self.request, attrs=None).order_by("order")
            activities = Activity.objects.get_objects_by_general_filtre(request=self.request, attrs=None).order_by("phase__order", "order")
            tasks = [elem for sous_liste in [_activity.task_set.get_queryset().order_by("phase__order", "activity__order", "order") for _activity in _activities] for elem in sous_liste]
        
        else:
            phases = Phase.objects.get_objects_by_general_filtre(request=self.request, attrs=None).order_by("order")
            activities = Activity.objects.get_objects_by_general_filtre(request=self.request, attrs=None).order_by("phase__order", "order")
            tasks = Task.objects.get_objects_by_general_filtre(request=self.request, attrs=None).order_by("phase__order", "activity__order", "order")

        datas = {'phases': [], 'activities': [], 'tasks': []}

        if _by_id:
            for p in phases:
                datas['phases'].append((p.id, p.name))
            
            for a in activities:
                datas['activities'].append((a.id, a.name))
            
            for t in tasks:
                datas['tasks'].append((t.id, t.name))
        else:
            for p in phases:
                datas['phases'].append((p.name, p.name))
            
            for a in activities:
                datas['activities'].append((a.name, a.name))
            
            for t in tasks:
                datas['tasks'].append((t.name, t.name))

        return self.render_to_json_response(datas, safe=False)



class GetChoicesForNextPhaseActivitiesTasksByIdView(AJAXRequestMixin, LoginRequiredMixin, JSONResponseMixin, generic.View):
    def get(self, request, *args, **kwargs):
        phase_id = self.request.GET.getlist('phases_id[]')
        activity_id = self.request.GET.getlist('activities_id[]')
        task_id = self.request.GET.getlist('tasks_id[]')

        if not phase_id and not activity_id and not task_id:
            phase_id = int(request.GET.get('phase_name') if request.GET.get('phase_name') else 0)
            activity_id = int(request.GET.get('activity_name') if request.GET.get('activity_name') else 0)
            task_id = int(request.GET.get('task_name') if request.GET.get('task_name') else 0)

        show_all_if_none = request.GET.get('show_all_if_none') in ('true', True)

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
            get_cascade_phase_activity_task_by_their_id(
                _get_on_list(phase_id), _get_on_list(activity_id), _get_on_list(task_id), 
                self.request.session.get('project_id'), 
                self.request.session.get('cycle_id'), show_all_if_none
            ), 
            safe=False
        )


class ValidateTaskView(AJAXRequestMixin, LoginRequiredMixin, JSONResponseMixin, generic.View):
    def _trigger_share_copy(self, request, task):
        """Résout les cibles de partage — PAR MODE, un même formulaire pouvant
        avoir des champs en modes différents (cf.
        ``form_design.group_share_paths_by_mode``) — pour la tâche couch qui
        vient d'être validée, et lance la copie en thread (une passe par mode
        présent, chacune vers ses propres cibles). ``task`` est le document
        CouchDB (dict-like) déjà mis à jour avec ``validated: True``. Aucun
        effet si la tâche n'a aucun champ partageable."""
        import json
        import threading
        from django.db import connections
        from process_manager.models import Task as TaskModel, TaskShareRecord
        from dashboard.utils import (
            canton_headquarters_village_ids, copy_shared_task_data,
            find_task_share_record, upsert_task_share_record,
        )
        from dashboard.process_manager.tasks.form_design import group_share_paths_by_mode

        task_sql_id = task.get('sql_id')
        source_adl = task.get('administrative_level_id')
        if not task_sql_id or not source_adl:
            return
        try:
            task_model = TaskModel.objects.get(id=task_sql_id)
        except TaskModel.DoesNotExist:
            return

        modes_present = group_share_paths_by_mode(task_model.form)
        if not modes_present:
            return

        project_id = request.session.get('project_id')
        cycle_id = request.session.get('cycle_id')
        # Identité du validateur — extraite ICI (pas dans `_worker`, qui
        # tourne dans un thread après la fin de la requête) pour l'entrée
        # `actions_by` de validation automatique quand toute la tâche est
        # partagée (cf. copy_shared_task_data / all_fields_shared).
        validated_by = {
            'user_name': request.user.username, 'user_id': request.user.id,
            'user_last_name': request.user.last_name, 'user_first_name': request.user.first_name,
            'user_email': request.user.email,
        }

        # Cibles choisies explicitement par mode (sélecteur web, un <select>
        # par mode présent) -> {"<mode>": ["<adl_id>", ...], ...}, envoyé en
        # JSON par task_detail_modal.js. Repli par mode sinon.
        explicit_by_mode = {}
        raw_json = request.GET.get('share_targets_json')
        if raw_json:
            try:
                parsed = json.loads(raw_json)
                if isinstance(parsed, dict):
                    explicit_by_mode = parsed
            except (TypeError, ValueError):
                explicit_by_mode = {}

        source_record = find_task_share_record(
            task_sql_id, project_id, source_adl, prefer_field='share_targets',
        )
        # share_targets du registre source : dict {mode: [ids]} désormais ;
        # tolère l'ancienne forme (liste nue = choix du facilitateur en mode
        # facilitator_then_validator, seul mode jamais alimenté par le mobile
        # avant ce changement).
        stored_targets = (source_record.share_targets if source_record else None) or {}
        if isinstance(stored_targets, list):
            stored_targets = {TaskModel.SHARE_MODE_FACILITATOR_THEN_VALIDATOR: stored_targets}

        targets_by_mode = {}
        for mode in modes_present:
            explicit = explicit_by_mode.get(mode)
            if isinstance(explicit, list) and explicit:
                targets_by_mode[mode] = [t for t in explicit if t]
                continue
            if mode == TaskModel.SHARE_MODE_FIXED_CANTON:
                targets_by_mode[mode] = canton_headquarters_village_ids(source_adl)
            elif mode == TaskModel.SHARE_MODE_FACILITATOR_THEN_VALIDATOR:
                # Repli sur le choix du facilitateur (envoyé via
                # ReportTaskCompletion, mobile) quand le validateur n'a pas
                # changé la sélection dans le sélecteur web.
                targets_by_mode[mode] = list(stored_targets.get(mode) or [])
            else:  # validator_only : rien sans sélection explicite du validateur
                targets_by_mode[mode] = []

        targets_by_mode = {m: t for m, t in targets_by_mode.items() if t}
        if not targets_by_mode:
            return

        merged_stored = dict(stored_targets)
        merged_stored.update(targets_by_mode)
        source_defaults = {'status': TaskShareRecord.STATUS_VALIDATED, 'share_targets': merged_stored}
        if cycle_id is not None:
            source_defaults['cycle_id'] = cycle_id
        upsert_task_share_record(task_sql_id, project_id, source_adl, defaults=source_defaults)

        def _worker():
            try:
                for mode, targets in targets_by_mode.items():
                    copy_shared_task_data(
                        task_sql_id, source_adl, targets, project_id, cycle_id, mode,
                        validated_by=validated_by,
                    )
            finally:
                for conn in connections.all():
                    conn.close()

        threading.Thread(target=_worker, daemon=True).start()

    def get(self, request, *args, **kwargs):
        no_sql_db_name = request.GET.get('no_sql_db_name')
        task_id = request.GET.get('task_id')
        in_validation_comment = request.GET.get('in_validation_comment')
        action_code = int(request.GET.get('action_code') if request.GET.get('action_code') else 0)
        message = None
        status = "ok"
        mail_message, sms_message = None, None
        previous_status = None
        
        try:

            project_mis = mis_objects_call.filter_objects(MisProject, name=self.request.session.get('project_name'))
            project_mis_id = project_mis.first().id if project_mis.count() >= 1 else 1

            nsc = NoSQLClient()
            db = nsc.get_db(no_sql_db_name)
            try:
                task = db[db.get_query_result({"type": "task", "_id": task_id})[:][0]['_id']]
            except Exception as exc:
                # print(exc)
                query_result = db.get_query_result({
                    "type": 'facilitator',
                    "$or": [
                        {"project_id": request.session.get('project_couch_id')},
                        {"projects_ids": {"$in": [request.session.get('project_couch_id')]}}
                    ]
                })[:]
                no_sql_dbs_names_with_village_ids, cvds, administratives_stabilized = get_search_for_stabilized_facilitator_dbs(project_mis_id, db[query_result[0]['_id']])
                db_name, query_result = get_db_task(no_sql_dbs_names_with_village_ids, task_id)
                
                nsc = NoSQLClient()
                db = nsc.get_db(db_name)
                if query_result:
                    task = db[query_result[0]['_id']]


            previous_status = task.get('validated')
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
                _data = {
                    "validated": bool(action_code),
                    "date_validated": date_validated if bool(action_code) else None,
                    "action_by": action_by,
                    "actions_by": actions_by
                }
                if "updated_after_invalidation" in task and not bool(action_code):
                    _data["updated_after_invalidation"] = False

                nsc.update_doc_uncontrolled(db, task['_id'], _data)

                # Partage entre villages sièges (Task.share_mode) : copie
                # UNIQUEMENT à la validation (pas à l'invalidation), en thread
                # daemon pour ne pas bloquer cette requête ni les autres
                # utilisateurs. Best-effort : une erreur ici ne doit jamais
                # affecter le message de validation renvoyé ci-dessous.
                if bool(action_code):
                    try:
                        self._trigger_share_copy(request, task)
                    except Exception:
                        logger.exception(
                            "ValidateTaskView: échec best-effort du déclenchement de la copie "
                            "de partage villages sièges (task_id=%s).", task_id,
                        )

                #Send Mail - SMS
                # Best-effort, comme _trigger_share_copy ci-dessus : la tâche est déjà
                # invalidée en base (nsc.update_doc_uncontrolled juste au-dessus) au
                # moment où ce bloc s'exécute -> une erreur ici (doc facilitateur
                # introuvable, envoi mail/SMS en échec, etc.) ne doit JAMAIS faire
                # remonter "Une erreur s'est produite" côté utilisateur pour une
                # invalidation qui, elle, a réellement réussi.
                if not bool(action_code):
                  try:
                    facilitator = db[db.get_query_result({"type": "facilitator"})[:][0]['_id']]
                    subject = f'{gettext_lazy("Task Invalided")} : {task.get("name")}'
                    administrative_region_name = get_administrative_region_name(task.get("administrative_level_id"))

                    facilitator_email = None
                    facilitator_object = Facilitator.objects.filter(id=facilitator['sql_id'], active=True).first()
                    assing_facilitator_object = None
                    if facilitator_object:
                        facilitator_email = facilitator_object.email


                        # assing_facilitator_object = mis_objects_call.filter_objects(
                        #     AssignAdministrativeLevelToFacilitator, 
                        #     administrative_level_id=int(task.get("administrative_level_id")),
                        #     facilitator_id=facilitator_object.id, 
                        #     project_id=project_mis_id, 
                        #     activated=True
                        # ).first()

                    # if not facilitator_object or not assing_facilitator_object:
                    facilitator_stabilized = None
                    try:
                        all_facilitators_worked_in_village = Facilitator.objects.filter(
                            facilitator_type='community_facilitator',
                            develop_mode=False, training_mode=False, 
                            active=True, 
                            projects__in=[self.request.session.get('project_id')]
                        ).filter(
                            Q(stabilization_administrative_ids__contains=[int(task.get("administrative_level_id"))]) |
                            Q(additional_administrative_ids__contains=[int(task.get("administrative_level_id"))])
                        ).distinct()
                        
                        # results = [
                        #     {'doc': doc}
                        #     for doc in grm_client.get_facilitator_by_village(int(task.get("administrative_level_id")))
                        # ]


                        # facilitator_email = facilitator.get("email")
                        # matching_docs = {}
                        # count = 0
                        # for row in results:
                        #     doc = row["doc"]
                        #     if doc.get("representative", {}).get("email") != facilitator_email:
                        #         if count == 0:
                        #             facilitator_stabilized = doc
                        #         matching_docs[doc['representative']['email']] = doc
                        #         count += 1

                        # try:
                        #     facilitator_stabilized = matching_docs[task['completed_history'][-1]['facilitator']['email']] #search the last facilitator who has update the task
                        # except:
                        #     if not facilitator_stabilized:
                        #         facilitator_stabilized = next(
                        #             (
                        #                 doc for doc in grm_client.get_facilitator_by_village(int(task.get("administrative_level_id")))
                        #                 if doc.get('representative', {}).get('email') != facilitator.get('email')
                        #             ),
                        #             None,
                        #         )

                        try:
                            facilitator_stabilized = all_facilitators_worked_in_village.get(email=task['completed_history'][-1]['facilitator']['email']) #search the last facilitator who has update the task
                        except:
                            if not facilitator_stabilized:
                                facilitator_stabilized = all_facilitators_worked_in_village.filter(stabilization_administrative_ids__contains=[int(task.get("administrative_level_id"))]).first()
                            if not facilitator_stabilized:
                                facilitator_stabilized = all_facilitators_worked_in_village.first()

                    except Exception as exc:
                        # print(exc)
                        pass
                
                    if facilitator_stabilized:
                        # facilitator_object = Facilitator.objects.filter(email=facilitator_stabilized['representative']['email']).first()
                        facilitator_object = facilitator_stabilized
                
                    msg = 'error'
                    try:
                        msg = send_email(
                            f'[COSO Apps : {datetime.now().strftime("%Y-%m-%d")}] {subject}',
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
                                    gettext_lazy("Facilitator Name"): facilitator_object.name,
                                    gettext_lazy("Facilitator Phone"): facilitator_object.phone,
                                    gettext_lazy("Facilitator Sex"): "F" if facilitator_object.sex == "Mme" else "M",
                                    gettext_lazy("Validator"): f"{request.user.last_name} {request.user.first_name}",
                                    gettext_lazy("Validator Type"): get_group_high(request.user),
                                    gettext_lazy("Validator Email"): request.user.email,
                                },
                                "url": f"{request.scheme}://{request.META['HTTP_HOST']}{reverse_lazy('dashboard:facilitators:detail', args=[no_sql_db_name])}"
                            },
                            list(set(
                                # Bug corrigé : englober values_list(...) dans une liste
                                # ([ ... ] + ...) mettait une LISTE (non hachable) dans le
                                # set() -> TypeError systématique ("unhashable type: 'list'"),
                                # avalé par le except ci-dessous mais empêchant l'envoi du
                                # mail à chaque invalidation.
                                list(all_facilitators_worked_in_village.values_list('email', flat=True)) +
                                ([facilitator_email, facilitator_object.email, request.user.email]
                                if facilitator_email
                                else [facilitator_object.email, request.user.email])
                            )),
                            project_name=task.get("project_name", self.request.session.get('project_name', 'COSO'))
                        )
                        mail_message = gettext_lazy("Mail sent successfully")
                    except Exception as exc:
                        # print(exc)
                        pass
                    if msg == 'error':
                        mail_message = gettext_lazy("An error occurred while sending the email")

                    try:
                        TWILIO_REGION = str(settings.TWILIO_REGION)
                        send_sms(
                            f"+{(facilitator_object.phone if (facilitator_object.phone and TWILIO_REGION in facilitator_object.phone and TWILIO_REGION == facilitator_object.phone[0:len(TWILIO_REGION)]) else (TWILIO_REGION+facilitator_object.phone))}", 
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
                        # print(exc)
                        sms_message = gettext_lazy("An error occurred while sending the sms")
                  except Exception:
                    logger.exception(
                        "ValidateTaskView: échec best-effort de la notification "
                        "mail/SMS d'invalidation (tâche déjà invalidée en base)."
                    )
                #End Send Mail - SMS


                message = gettext_lazy("Task validated").__str__() if bool(action_code) else gettext_lazy("Task not validated").__str__()
            else:
                message = gettext_lazy("The task isn't completed").__str__()
                status = "error"
        except Exception as exc:
            # Auparavant avalée sans trace -> aucun moyen de diagnostiquer un
            # "Une erreur s'est produite" côté utilisateur. Journalisée pour de
            # futurs diagnostics (le message renvoyé au navigateur ne change pas).
            logger.exception("ValidateTaskView.get a échoué (task_id=%s, action_code=%s)", task_id, action_code)
            message = gettext_lazy("An error has occurred...").__str__()
            status = "error"

        return self.render_to_json_response(
            {
                "message": message, "status": status, 
                "sms_message": sms_message, "mail_message": mail_message,
                "previous_status": previous_status
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
            try:
                task = db[db.get_query_result({"type": "task", "_id": task_id})[:][0]['_id']]
            except Exception as exc:
                # print(exc)
                project_mis = mis_objects_call.filter_objects(MisProject, name=self.request.session.get('project_name'))
                project_mis_id = project_mis.first().id if project_mis.count() >= 1 else 1
                query_result = db.get_query_result({
                    "type": 'facilitator',
                    "$or": [
                        {"project_id": request.session.get('project_couch_id')},
                        {"projects_ids": {"$in": [request.session.get('project_couch_id')]}}
                    ]
                })[:]
                no_sql_dbs_names_with_village_ids, cvds, administratives_stabilized = get_search_for_stabilized_facilitator_dbs(project_mis_id, db[query_result[0]['_id']])
                db_name, query_result = get_db_task(no_sql_dbs_names_with_village_ids, task_id)
                
                nsc = NoSQLClient()
                db = nsc.get_db(db_name)
                if query_result:
                    task = db[query_result[0]['_id']]


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
            actions_by.insert(0, action_complete_by)
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

class ProjectListView(PageMixin, LoginRequiredMixin, generic.ListView):
    model = Project
    template_name = 'process_manager/list.html'
    context_object_name = 'projects'
    title = gettext_lazy('Projects')
    active_level1 = 'projects'
    breadcrumb = [
       {
                'url': '',
                'title': title
            },
    ]

    def get(self, request, *args, **kwargs):
        projects = self.get_queryset().filter(users__in=[self.request.user.id])
        project_id = self.request.GET.get('project_id')
        
        if project_id is not None:
            projects = projects.filter(id=int(project_id))
        if len(projects) == 1:
            self.request.session['project_id'] = projects[0].id
            self.request.session['project_couch_id'] = projects[0].couch_id
            self.request.session['project_name'] = projects[0].name
            
            self.request.session['project_mis_id'] = mis_objects_call.get_object(ProjectMis, name=projects[0].name).id

            cycles = Cycle.objects.filter(project_id=projects[0].id).order_by('order')
            if cycles.exists():
                self.request.session['cycle_id'] = cycles[0].id
                self.request.session['cycle_couch_id'] = cycles[0].couch_id
                self.request.session['cycle_name'] = cycles[0].name
                
                self.request.session['cycle_mis_id'] = mis_objects_call.get_object(CycleMis, name=cycles[0].name, project_id=self.request.session['project_mis_id']).id
                if len(cycles) != 1:
                    messages.success(request, "We have detected several cycles for this project. We have chosen the first cycle by default.")
            else:
                messages.success(request, "No cycle is defined for this project")

            
            tree_structure_projects = projects[0].build_the_tree_structure()
            self.request.session['tree_structure_projects_ids'] = [p.id for p in tree_structure_projects]
            self.request.session['tree_structure_projects_names'] = [p.name for p in tree_structure_projects]

            self.request.session['tree_structure_projects_mis_ids'] = [mis_objects_call.get_object(ProjectMis, name=p.name).id for p in tree_structure_projects]

            if self.request.user.groups.filter(name__in=["Supervisor"]).exists() and hasattr(self.request.user, 'email'):
                facilitator_grm = grm_client.get_facilitator_by_email(self.request.user.email)
                grm_client.attach_administrative_regions_objects(facilitator_grm)
                # administratives_stabilized = facilitator_grm['administrative_regions']
                administrative_regions_objects = facilitator_grm.get('administrative_regions_objects') if facilitator_grm else None
                self.request.session['cantons_stabilized_ids'] = list(set(
                    # (administratives_stabilized if administratives_stabilized else []) +
                    list(itertools.chain(*[[str(ad['id'])] for ad in (administrative_regions_objects if administrative_regions_objects else []) if ad and type(ad) is dict and 'id' in ad]))
                ))

            next_page = self.request.GET.get('next')
            if next_page:
                return HttpResponseRedirect(resolve_url(next_page or settings.LOGIN_REDIRECT_URL))
            return redirect('dashboard:facilitators:list')
        
        return super().get(request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['projects'] = list(self.object_list.filter(users__in=[self.request.user.id]))
        context['next_url'] = self.request.GET.get('next')

        return context