from rest_framework.views import APIView
from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response
from django.utils import timezone
from django.utils.translation import gettext_lazy
from django.urls import reverse_lazy
from datetime import datetime
import locale

from dashboard.facilitators.repository.db_facilitator_repository import FacilitatorRepository
# from dashboard.facilitators.repository.facilitator_criteria import FacilitatorCriteria
from authentication.models import Facilitator
from planning.serializers import *
from planning.models import *
from authentication.api.auth.login import CheckUserSerializer
from cdd.my_librairies.mail.send_mail import send_email



# =================================== Save =================================================================
class RestSaveActivity(APIView):
    throttle_classes = ()
    permission_classes = ()
    serializer_class = SaveActivitySerializer
    
    def post(self, request, *args, **kwargs):
        # try:
            id = request.data.get('id')
            user = None

            if id:
                activity = Activity.objects.get(id=id)
                if activity.validated and not (request.data.get('comment') or request.data.get('undo_comment')):
                    return Response(
                        {'error': "validated"}, 
                        status=status.HTTP_208_ALREADY_REPORTED
                    )
                serializer = self.serializer_class(activity, data=request.data, context={'request': request})
            else:
                serializer = self.serializer_class(data=request.data, context={'request': request})
                
            serializer.is_valid(raise_exception=True)
            validated_data = serializer.validated_data
            
            s = CheckUserSerializer(request.data).data

            activity = serializer.save()
            
            if activity.validated == False:
                activity.edit_after_invalidation = True
                activity = activity.save_and_return_object(user=self.request.user)

                try:
                    locale.setlocale(locale.LC_TIME, 'fr_FR.UTF-8')
                    activity_plan_date = (
                        f'{activity.planned_datetime_start.strftime("%l")} {gettext_lazy("the")} {activity.planned_datetime_start.strftime("%d %F %Y")}' if activity.type != 'vacation' else \
                        f'{activity.planned_datetime_start.strftime("%l")} {gettext_lazy("the")} {activity.planned_datetime_start.strftime("%d %F %Y")} {gettext_lazy("to")} {activity.planned_datetime_end.strftime("%l")} {gettext_lazy("the")} {activity.planned_datetime_end.strftime("%d %F %Y")}'
                    )
                    msg = send_email(
                        f'{gettext_lazy("Activity Invalided")} : {activity.name} ({activity_plan_date})',
                        "mail/send/comment",
                        {
                            "datas": {
                                gettext_lazy("Subject "): gettext_lazy("Invalidated activity modified by planner"), 
                                gettext_lazy("Activity"): activity.name,
                                gettext_lazy("Description"): activity.description,
                                gettext_lazy("Planned on"): activity_plan_date,
                                gettext_lazy("Updated on"): f'{activity.updated_date.strftime("%l")} {gettext_lazy("the")} {activity.updated_date.strftime("%d %F %Y")}',
                                gettext_lazy("Location"): ", ".join([v["name"] for v in activity.administrative_levels]) if activity.administrative_levels else "",
                            },
                            "user": {
                                gettext_lazy("Planner"): f"{activity.user.last_name} {activity.user.first_name}" if activity.user else (activity.facilitator.name if activity.facilitator else None),
                                gettext_lazy("Email"): activity.user.email if activity.user else (activity.facilitator.email if activity.facilitator else None),
                            },
                            "url": f"{request.scheme}://{request.META['HTTP_HOST']}{reverse_lazy('dashboard:planning:list')}"
                        },
                        [e for e in list([
                            activity.user.email if activity.user else (activity.facilitator.email if activity.facilitator else None)
                        ] + [(v.user.email if v.user else (v.facilitator.email if v.facilitator else None)) for v in activity.get_activities_validate()]) if e],
                        []
                    )
                    mail_message = gettext_lazy("Mail sent successfully")
                except:
                    mail_message = gettext_lazy("An error occurred while sending the email")
                
            if not id:
                if request.data.get('username'):
                    user = User.objects.filter(username=request.data.get('username')).first()
                    user = Facilitator.objects.filter(
                        username=request.data.get('username'),
                    ).first() if not user else user
                if not user and request.data.get('email'):
                    user = User.objects.filter(email=request.data.get('email')).first()
                    user = Facilitator.objects.filter(
                            email=request.data.get('email'),
                        ).first() if not user else user
                
                if user and not hasattr(user, 'no_sql_user'):
                    activity.user = user
                else:
                    activity.facilitator = user

                activity = activity.save_and_return_object(user=self.request.user)
            
            return Response(
                ActivitySerializer(
                    activity,
                    many=False).data, 
                status=status.HTTP_200_OK
            )
        # except Exception as exc:
        #     return Response(
        #         {'error': exc.__str__()}, 
        #         status=status.HTTP_404_NOT_FOUND
        #     )


class RestSaveActivityFile(APIView):
    throttle_classes = ()
    permission_classes = ()
    serializer_class = ActivityFileSerializer
    
    def post(self, request, *args, **kwargs):
        try:
            serializer = self.serializer_class(data=request.data, context={'request': request})

            serializer.is_valid(raise_exception=True)
            validated_data = serializer.validated_data
            file = serializer.save()

            return Response(
                ActivityFileSerializer(
                    ActivityFile.objects.get(id=file.pk),
                    many=False).data, 
                status=status.HTTP_200_OK
            )
        except Exception as exc:
            return Response(
                {'error': exc.__str__()}, 
                status=status.HTTP_404_NOT_FOUND
            )

# class RestSaveActivityComment(APIView):
#     throttle_classes = ()
#     permission_classes = ()
#     serializer_class = ActivityCommentSerializer
    
#     def post(self, request, *args, **kwargs):
#         try:
#             serializer = self.serializer_class(data=request.data, context={'request': request})

#             serializer.is_valid(raise_exception=True)
#             validated_data = serializer.validated_data
#             comment = serializer.save()

#             return Response(
#                 ActivityCommentSerializer(
#                     ActivityComment.objects.get(id=comment.pk),
#                     many=False).data, 
#                 status=status.HTTP_200_OK
#             )
#         except Exception as exc:
#             return Response(
#                 {'error': exc.__str__()}, 
#                 status=status.HTTP_404_NOT_FOUND
#             )

class RestSaveActivityComment(APIView):
    throttle_classes = ()
    permission_classes = ()
    # serializer_class = ActivityCommentSerializer
    
    # def post(self, request):
    #     data = request.data
    #     serializer = ActivityCommentSerializer(data=data, many=True)

    #     if serializer.is_valid():
    #         serializer.save()
    #         return Response(serializer.data, status=status.HTTP_201_CREATED)
    #     else:
    #         return Response(
    #             {'error': 'ok'}, 
    #             status=status.HTTP_404_NOT_FOUND
    #         )

    def post(self, request):
        _data = request.data
        
        if type(_data) is dict:
            data = [v for k, v in list(_data.items()) if str(k).isdigit()]
        else:
            data = _data
            
        # Comment
        data_comments = [item for item in data if 'validated' not in item]
        task_ids = [item.get('id') for item in data_comments if 'id' in item]
        if task_ids:
            existing_tasks = ActivityComment.objects.filter(id__in=task_ids)

            existing_tasks_dict = {task.id: task for task in existing_tasks}

            serializers = []

            for item in data_comments:
                task_id = item.get('id')
                task_instance = existing_tasks_dict.get(task_id) if task_id else None

                serializer = SaveActivityCommentSerializer(instance=task_instance, data=item)
                serializers.append(serializer)

            if all(serializer.is_valid() for serializer in serializers):
                for serializer in serializers:
                    serializer.save()
                # return Response([serializer.data for serializer in serializers], status=status.HTTP_200_OK)
            else:
                errors = [serializer.errors for serializer in serializers]
                # return Response(errors, status=status.HTTP_400_BAD_REQUEST)
        else:
            serializer = SaveActivityCommentSerializer(data=data_comments, many=True)

            if serializer.is_valid():
                serializer.save()
                # return Response(serializer.data, status=status.HTTP_201_CREATED)
            # else:
            #     return Response(
            #         {'error': 'ok'}, 
            #         status=status.HTTP_404_NOT_FOUND
            #     )

        # Validation
        data_validations = [item for item in data if 'validated' in item]
        task_ids = [item.get('id') for item in data_validations if 'id' in item]
        if task_ids:
            existing_tasks = ActivityValidate.objects.filter(id__in=task_ids)

            existing_tasks_dict = {task.id: task for task in existing_tasks}

            serializers = []

            for item in data_validations:
                task_id = item.get('id')
                task_instance = existing_tasks_dict.get(task_id) if task_id else None

                serializer = SaveActivityValidateSerializer(instance=task_instance, data=item)
                serializers.append(serializer)

            if all(serializer.is_valid() for serializer in serializers):
                for serializer in serializers:
                    serializer.save()
                # return Response([serializer.data for serializer in serializers], status=status.HTTP_200_OK)
            else:
                errors = [serializer.errors for serializer in serializers]
                # return Response(errors, status=status.HTTP_400_BAD_REQUEST)
        else:
            serializer = SaveActivityValidateSerializer(data=data_validations, many=True)

            if serializer.is_valid():
                serializer.save()
                # return Response(serializer.data, status=status.HTTP_201_CREATED)
            # else:
            #     return Response(
            #         {'error': 'ok'}, 
            #         status=status.HTTP_404_NOT_FOUND
            #     )
        s = []
        if data and len(data) > 0 and 'activity' in data[0]:
            a = Activity.objects.get(id=data[0]['activity'])
            activities_validates = ActivityValidateSerializer(a.get_activities_validate(), many=True).data
            comments = ActivityCommentSerializer(a.get_comments(), many=True).data

            s = sorted(
                (list(comments) + list(activities_validates)), key=lambda obj: obj.get('created_date'), reverse=True
            )

        return Response(
            s, 
            status=status.HTTP_200_OK
        )




    # def post(self, request, *args, **kwargs):
    #     try:
    #         serializer = self.serializer_class(data=request.data, context={'request': request})

    #         serializer.is_valid(raise_exception=True)
    #         validated_data = serializer.validated_data
    #         comment = serializer.save()

    #         return Response(
    #             ActivityCommentSerializer(
    #                 ActivityComment.objects.get(id=comment.pk),
    #                 many=False).data, 
    #             status=status.HTTP_200_OK
    #         )
    #     except Exception as exc:
    #         return Response(
    #             {'error': exc.__str__()}, 
    #             status=status.HTTP_404_NOT_FOUND
    #         )


# =================================== Get =================================================================

class RestGetActivityByAttributes(APIView):
    throttle_classes = ()
    permission_classes = ()
    
    def post(self, request, *args, **kwargs):
        try:
            return Response(
                ActivitySerializer(
                    Activity.objects.filter(**dict(request.data)),
                    many=True).data, 
                status=status.HTTP_200_OK
            )
        except Exception as exc:
            print(exc)
            return Response(
                {'error': exc.__str__()}, 
                status=status.HTTP_404_NOT_FOUND
            )

class RestGetActivityById(APIView):
    throttle_classes = ()
    permission_classes = ()
    
    def post(self, request, pk, *args, **kwargs):
        print(Activity.objects.get(id=pk))
        try:
            return Response(
                ActivitySerializer(
                    Activity.objects.get(id=pk),
                    many=False).data, 
                status=status.HTTP_200_OK
            )
        except Exception as exc:
            return Response(
                {'error': exc.__str__()}, 
                status=status.HTTP_404_NOT_FOUND
            )


# =================================== Delete =================================================================

class DeleteActivityAPIView(APIView):
    throttle_classes = ()
    permission_classes = ()
    serializer_class = CheckUserSerializer
    
    def post(self, request, *args, **kwargs):
        try:
            serializer = self.serializer_class(data=request.data, context={'request': request})
            serializer.is_valid(raise_exception=True)
            user = serializer.validated_data

            username = request.data['username']
            if user and username:
                _ = Activity.objects.get(Q(user__username=username) | Q(facilitator__username=username), id=request.data['id'], project_id=request.data['project'])
                
                if _.validated:
                    return Response(
                            {'error': "validated"}, 
                            status=status.HTTP_208_ALREADY_REPORTED
                        )
                _.delete()
                return Response(
                    {'success': 'deleted'}, 
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {'error': exc.__str__()}, 
                    status=status.HTTP_404_NOT_FOUND
                )
        except Exception as exc:
            return Response(
                {'error': exc.__str__()}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
class DeleteActivityFileAPIView(APIView):
    throttle_classes = ()
    permission_classes = ()
    serializer_class = CheckUserSerializer
    
    def post(self, request, *args, **kwargs):
        try:
            serializer = self.serializer_class(data=request.data, context={'request': request})
            serializer.is_valid(raise_exception=True)
            user = serializer.validated_data
            print(request.data)
            username = request.data['username']
            _ = ActivityFile.objects.get(Q(activity__user__username=username) | Q(activity__facilitator__username=username), id=request.data['id']).delete()
            return Response(
                {'success': 'deleted'}, 
                status=status.HTTP_200_OK
            )
        except Exception as exc:
            print(exc)
            return Response(
                {'error': exc.__str__()}, 
                status=status.HTTP_404_NOT_FOUND
            )