import json
from django.http import HttpResponse
from cdd.my_librairies import convert_file_to_dict

# @csrf_exempt
def get_excel_sheets_names(request):
    names = []
    if request.method == "POST":
        names = convert_file_to_dict.get_excel_sheets_names(request.FILES.get('file'))
    return HttpResponse(json.dumps(
        {"names": names}
        ), content_type="application/json")


