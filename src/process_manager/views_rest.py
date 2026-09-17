from rest_framework import status
from rest_framework.response import Response

from process_manager.serializers import SaveFormDatasSerializer, ProjectSerializer
from no_sql_client import NoSQLClient
from process_manager.models import Project, Facilitator, Task, TaskShareRecord
from django.db.models import Q

from rest_framework.generics import ListAPIView
from rest_framework.views import APIView


class SaveFormDatas(APIView):
    throttle_classes = ()
    permission_classes = ()
    # parser_classes = (parsers.FormParser, parsers.MultiPartParser, parsers.JSONParser,)
    # renderer_classes = (renderers.JSONRenderer,)
    serializer_class = SaveFormDatasSerializer

    # def get_serializer_context(self):
    #     return {
    #         'request': self.request,
    #         'format': self.format_kwarg,
    #         'view': self
    #     }

    # def get_serializer(self, *args, **kwargs):
    #     kwargs['context'] = self.get_serializer_context()
    #     return self.serializer_class(*args, **kwargs)

    # @extend_schema(
    #     request=SaveFormDatasSerializer,
    # )
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        has_error = False
        nsc = NoSQLClient()
        facilitator_database = nsc.get_db(serializer.validated_data['no_sql_db_name'])
        for task in serializer.validated_data['tasks']:
            try:
                fc_task = facilitator_database.get_query_result({"type": "task", "_id": task['_id']})[0]
                t = fc_task[0]
                t["attachments"] = task['attachments']
                t["form_response"] = task['form_response']
                t["last_updated"] = task['last_updated']
                if not t["completed"]:
                    t["completed_date"] = task['completed_date']
                    t["completed"] = task['completed']

                nsc.update_cloudant_document(facilitator_database,  t["_id"], t)
            except Exception as exc:
                has_error = True
        
        return Response({'status': 'ok', 'has_error': has_error}, status=status.HTTP_200_OK)


class SaveGeolocationFormDatas(APIView):
    throttle_classes = ()
    permission_classes = ()
    serializer_class = SaveFormDatasSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        has_error = False
        nsc = NoSQLClient()
        facilitator_database = nsc.get_db(serializer.validated_data['no_sql_db_name'])
        for task in serializer.validated_data['tasks']:
            try:
                fc_task = facilitator_database.get_query_result({"type": "geolocation", "_id": task['_id']})[0]
                t = fc_task[0]
                t["administrativelevels"] = task['administrativelevels']
                t["others"] = task['others']
                t["synced"] = True

                nsc.update_cloudant_document(facilitator_database,  t["_id"], t)
            except Exception as exc:
                has_error = True
        
        return Response({'status': 'ok', 'has_error': has_error}, status=status.HTTP_200_OK)



class ReportTaskCompletion(APIView):
    """Appelée par le mobile juste après son écriture directe dans CouchDB
    (``insertTaskToLocalDb``), en plus de celle-ci — best-effort, ne bloque
    jamais l'app. Tient à jour ``TaskShareRecord`` (le "registre" des tâches
    "village siège" partageables : ``Task.share_mode != 'none'``), utilisé par
    la copie à la validation et par ``PullableTaskSource``/``PullTaskData``.
    Sans effet (``tracked: False``) si la tâche n'est pas partageable."""
    throttle_classes = ()
    permission_classes = ()

    def post(self, request, *args, **kwargs):
        from dashboard.process_manager.tasks.form_design import extract_share_values, has_share_fields

        data = request.data or {}
        task_sql_id = data.get('task_sql_id')
        administrative_level_id = data.get('administrative_level_id')
        project_id = data.get('project_id')
        cycle_id = data.get('cycle_id') or None
        if not (task_sql_id and administrative_level_id is not None and project_id):
            return Response(
                {'ok': False, 'error': 'task_sql_id, administrative_level_id et project_id sont requis.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            task = Task.objects.get(id=task_sql_id)
        except Task.DoesNotExist:
            return Response({'ok': False, 'error': 'Tâche introuvable.'}, status=status.HTTP_404_NOT_FOUND)

        # Le mode de partage est porté PAR CHAMP (form_design.group_share_paths_by_mode) ;
        # "partageable" = au moins un champ marqué share, quel que soit son mode.
        if not has_share_fields(task.form):
            return Response({'ok': True, 'tracked': False})

        facilitator_sql_id = (data.get('facilitator') or {}).get('sql_id') or data.get('facilitator_sql_id')
        facilitator = Facilitator.objects.filter(id=facilitator_sql_id).first() if facilitator_sql_id else None
        completed = bool(data.get('completed'))
        form_response = data.get('form_response') or []
        share_targets = data.get('share_targets')

        defaults = {
            'couch_task_id': data.get('couch_task_id') or '',
            'status': TaskShareRecord.STATUS_COMPLETED if completed else TaskShareRecord.STATUS_IN_PROGRESS,
        }
        if cycle_id is not None:
            defaults['cycle_id'] = cycle_id
        if facilitator:
            defaults['facilitator'] = facilitator
        if completed:
            values = extract_share_values(task.form, form_response)
            if values:
                defaults['share_values'] = values
        if isinstance(share_targets, list) and share_targets:
            # Historiquement le seul expéditeur possible de ce champ (mobile,
            # aucune UI de choix de mode) -> toujours interprété comme les
            # cibles choisies par le facilitateur en mode
            # facilitator_then_validator (forme {mode: [ids]}, cf.
            # ValidateTaskView._trigger_share_copy).
            defaults['share_targets'] = {
                Task.SHARE_MODE_FACILITATOR_THEN_VALIDATOR: [t for t in share_targets if t is not None],
            }

        from dashboard.utils import upsert_task_share_record

        record, _created = upsert_task_share_record(
            task.id, project_id, administrative_level_id, defaults=defaults,
        )
        return Response({'ok': True, 'tracked': True, 'status': record.status})


class PullableTaskSource(APIView):
    """Existe-t-il une tâche jumelle (même tâche/projet/cycle, autre village)
    déjà achevée (ou validée) dont les champs "share" peuvent être chargés
    dans la tâche courante, pas encore renseignée ? Alimente le bouton mobile
    « Charger les données »."""
    throttle_classes = ()
    permission_classes = ()

    def get(self, request, *args, **kwargs):
        task_sql_id = request.GET.get('task_sql_id')
        administrative_level_id = request.GET.get('administrative_level_id')
        project_id = request.GET.get('project_id')
        cycle_id = request.GET.get('cycle_id') or None
        if not (task_sql_id and administrative_level_id and project_id):
            return Response({'found': False})

        from dashboard.process_manager.tasks.form_design import has_share_fields

        task = Task.objects.filter(id=task_sql_id).first()
        if not task or not has_share_fields(task.form):
            return Response({'found': False})

        # NB : `cycle_id` n'est PLUS utilisé pour filtrer ici — le mobile ne
        # l'envoie jamais et un même (tâche, village) peut se retrouver
        # scindé en plusieurs lignes de cycles différents (cf.
        # dashboard.utils.upsert_task_share_record) ; on préfère explicitement
        # parmi les candidats celui qui porte réellement des `share_values`
        # plutôt que le plus récemment synchronisé (qui peut être une ligne
        # "validée" sans aucune valeur, cf. bug réel constaté task 102).
        candidates = list(TaskShareRecord.objects.filter(
            task_id=task_sql_id, project_id=project_id,
            status__in=[TaskShareRecord.STATUS_COMPLETED, TaskShareRecord.STATUS_VALIDATED],
        ).exclude(administrative_level_id=administrative_level_id).order_by('-last_synced'))
        record = next((r for r in candidates if r.share_values), None)
        if not record:
            return Response({'found': False})

        source_label = None
        try:
            from administrativelevels.models import AdministrativeLevel
            adl = AdministrativeLevel.objects.using('mis').filter(id=record.administrative_level_id).first()
            source_label = adl.name if adl else None
        except Exception:
            pass

        return Response({
            'found': True,
            'source_administrative_level_id': record.administrative_level_id,
            'source_label': source_label,
            'share_values': record.share_values,
            'status': record.status,
        })


class PullTaskData(APIView):
    """Fusionne les valeurs partageables d'une tâche jumelle déjà achevée dans
    la tâche cible (non encore renseignée), directement dans la base CouchDB
    du facilitateur qui appelle (``target_no_sql_db_name``) — le mobile n'a
    besoin d'aucun accès à la base du facilitateur source."""
    throttle_classes = ()
    permission_classes = ()

    def post(self, request, *args, **kwargs):
        from dashboard.process_manager.tasks.form_design import merge_share_values, has_share_fields
        from dashboard.utils import _share_history_entry, find_task_share_record, upsert_task_share_record
        from administrativelevels.models import AdministrativeLevel

        data = request.data or {}
        task_sql_id = data.get('task_sql_id')
        target_administrative_level_id = data.get('target_administrative_level_id')
        target_couch_task_id = data.get('target_couch_task_id')
        target_no_sql_db_name = data.get('target_no_sql_db_name')
        source_administrative_level_id = data.get('source_administrative_level_id')
        project_id = data.get('project_id')
        cycle_id = data.get('cycle_id') or None

        if not (task_sql_id and target_administrative_level_id and target_couch_task_id and target_no_sql_db_name):
            return Response({'ok': False, 'error': 'Paramètres manquants.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            task = Task.objects.get(id=task_sql_id)
        except Task.DoesNotExist:
            return Response({'ok': False, 'error': 'Tâche introuvable.'}, status=status.HTTP_404_NOT_FOUND)
        if not has_share_fields(task.form):
            return Response({'ok': False, 'error': 'Cette tâche ne permet pas le partage.'}, status=status.HTTP_400_BAD_REQUEST)

        source_record = find_task_share_record(
            task_sql_id, project_id, source_administrative_level_id, prefer_field='share_values',
        )
        values = source_record.share_values if source_record else None
        if not values:
            return Response(
                {'ok': False, 'error': 'Aucune donnée partageable trouvée pour cette source.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        nsc = NoSQLClient()
        try:
            db = nsc.get_db(target_no_sql_db_name)
            doc = db[target_couch_task_id]
        except Exception:
            return Response(
                {'ok': False, 'error': 'Tâche cible introuvable dans CouchDB.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        merged_response = merge_share_values(task.form, doc.get('form_response') or [], values)
        source_label = None
        try:
            source_label = AdministrativeLevel.objects.using('mis').filter(
                id=source_administrative_level_id,
            ).values_list('name', flat=True).first()
        except Exception:
            pass
        history_entry = _share_history_entry(
            'pulled_by_facilitator', source_administrative_level_id, source_label,
            source_record.facilitator if source_record.facilitator_id else None, values.keys(),
        )
        nsc.update_doc_uncontrolled(db, doc['_id'], {
            "form_response": merged_response,
            "share_history": (doc.get('share_history') or []) + [history_entry],
        })

        pull_defaults = {'couch_task_id': target_couch_task_id, 'share_values': values}
        if cycle_id is not None:
            pull_defaults['cycle_id'] = cycle_id
        upsert_task_share_record(
            task_sql_id, project_id, target_administrative_level_id, defaults=pull_defaults,
        )

        return Response({'ok': True, 'form_response': merged_response, 'values': values})


class RestGetProjects(APIView):
    throttle_classes = ()
    permission_classes = ()
    
    def post(self, request, *args, **kwargs):
        try:
            return Response(
                ProjectSerializer(
                    Project.objects.all().order_by('name'),
                    many=True).data, 
                status=status.HTTP_200_OK
            )
        except Exception as exc:
            return Response(
                {'error': exc.__str__()}, 
                status=status.HTTP_404_NOT_FOUND
            )


class FacilitatorProjectListView(ListAPIView):
    serializer_class = ProjectSerializer
    queryset = Project.objects.all()
    def get_queryset(self):
        username = self.request.GET.get('username')
        return list(set(list(super().get_queryset().filter(Q(facilitators__username=username) | Q(facilitators__email=username) | Q(users__username=username) | Q(users__email=username)))))


class FacilitatorNOSQLDBListView(APIView):
    
    def get(self, request, *args, **kwargs):
        username = self.request.GET.get('username')
        try:
            no_sql_dbs_names = Facilitator.objects.get(username=username).no_sql_dbs_names
            return Response(
                list(set(no_sql_dbs_names if no_sql_dbs_names else [])), 
                status=status.HTTP_200_OK
            )
        except Exception as exc:
            return Response(
                {'error': exc.__str__()}, 
                status=status.HTTP_404_NOT_FOUND
            )