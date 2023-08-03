from drf_spectacular.utils import extend_schema
from rest_framework import parsers, renderers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from process_manager.serializers import SaveFormDatasSerializer
from no_sql_client import NoSQLClient


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
                t["completed_date"] = task['completed_date']
                t["completed"] = task['completed']
                t["last_updated"] = task['last_updated']

                nsc.update_cloudant_document(facilitator_database,  t["_id"], t)
            except Exception as exc:
                has_error = True
        
        return Response({'status': 'ok', 'has_error': has_error}, status=status.HTTP_200_OK)
