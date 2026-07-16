from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import get_template
from process_manager.models import EmailAddressesWhichSendEmails

def send_email(
        subject, template_path_without_extension, datas, 
        to,
        cc = [],
        project_name = None):
    """
    [
            "sig.anadeb@gmail.com", 
            "cosotogosig@gmail.com", 
            "palerbo@gmail.com", 
            "gounsougleyename@yahoo.fr", 
            "mass.zato36@gmail.com"
    ]
    """
#     to = ['adaboub20100@gmail.com']
#     cc = []

    if settings.DEBUG:
        to = [settings.RECIPIENT_EMAIL_DEFAULT]
        cc = [settings.RECIPIENT_EMAIL_DEFAULT]
    
    if not cc:
        e = EmailAddressesWhichSendEmails.objects.filter(name="task_invalidated_coso", project__name=project_name).first()
        if e:
            cc = e.email_addresses if e.email_addresses else []

    try:
        plaintext = get_template(template_path_without_extension+'.txt')
        htmly     = get_template(template_path_without_extension+'.html')

        text_content = plaintext.render(datas)
        html_content = htmly.render(datas)
        msg = EmailMultiAlternatives(subject, text_content, to=to, cc=cc)
        msg.attach_alternative(html_content, "text/html")
        msg.content_subtype = 'html'
        result = msg.send()

        return "success"
    except Exception as e:
        return "error"
    
