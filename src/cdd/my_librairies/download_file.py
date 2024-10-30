import os
from django.conf import settings
from django.http import HttpResponse, Http404
from sys import platform

def download(request, path, content_type="application/pdf", param_download=True):
    file_path = os.path.join(settings.MEDIA_ROOT, path)
    if os.path.exists(file_path):
        with open(file_path, 'rb') as fh:
            response = HttpResponse(fh.read(), content_type)
            # response['Content-Disposition'] = 'inline; filename=' + os.path.basename(file_path)
            content = 'inline; filename=' + os.path.basename(file_path)
            if param_download:
                content = "attachment; filename=" + os.path.basename(file_path)
            response['Content-Disposition'] = content
            return response
    raise Http404


def download_file_view(request, path, content_type):
    if path:
        if platform == "win32":
            # windows
            path = path.replace("___", "\\")
        else:
            path = path.replace('___', '/')
            
    if content_type in (None, 'None'):
        content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    
    return download(
        request, 
        path,
        content_type
    )