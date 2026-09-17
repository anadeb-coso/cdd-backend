"""Vues de conversion PDF <-> Word à la demande (bouton "Convertir", un clic).

Mêmes conventions que ``download_file.download_from_url`` (GET ``?url=``,
proxy vers la ressource distante, réponse en pièce jointe) mais protégées par
``@login_required`` : contrairement à un simple relais de téléchargement, une
conversion est coûteuse (PyMuPDF / sous-processus LibreOffice) — pas de raison
de l'exposer sans authentification alors que toutes les pages qui l'utilisent
exigent déjà une session connectée."""
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, Http404

from cdd.my_librairies.doc_convert import (
    DocConversionError, convert_pdf_to_docx_bytes, convert_docx_to_pdf_bytes,
)


def _source_basename(url):
    name = url.split("/")[-1].split("?")[0]
    return name.rsplit(".", 1)[0] if "." in name else name


@login_required
def convert_pdf_to_word(request):
    url = request.GET.get('url')
    if not url:
        raise Http404("Specify the url")
    try:
        content = convert_pdf_to_docx_bytes(url)
    except DocConversionError as exc:
        return HttpResponse(str(exc), status=502, content_type="text/plain; charset=utf-8")
    filename = f"{_source_basename(url) or 'document'}.docx"
    response = HttpResponse(
        content,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
def convert_word_to_pdf(request):
    url = request.GET.get('url')
    if not url:
        raise Http404("Specify the url")
    try:
        content = convert_docx_to_pdf_bytes(url)
    except DocConversionError as exc:
        return HttpResponse(str(exc), status=502, content_type="text/plain; charset=utf-8")
    filename = f"{_source_basename(url) or 'document'}.pdf"
    response = HttpResponse(content, content_type="application/pdf")
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
