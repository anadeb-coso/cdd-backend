from django.utils.translation import gettext_lazy as _
from django.core.mail import EmailMultiAlternatives
from django.template.loader import get_template


def send_email(
        subject, template_path_without_extension, datas, 
        to,
        cc = [
            #"sig.anadeb@gmail.com", "cosotogosig@gmail.com"#, "palerbo@gmail.com", "gounsougleyename@yahoo.fr", "mass.zato36@gmail.com"
        ]):
    
    try:
        plaintext = get_template(template_path_without_extension+'.txt')
        htmly     = get_template(template_path_without_extension+'.html')

        text_content = plaintext.render(datas)
        html_content = htmly.render(datas)
        msg = EmailMultiAlternatives(subject, text_content, to=to, cc=cc)
        msg.attach_alternative(html_content, "text/html")
        msg.send()

        return "success"
    except Exception as e:
        return "error"
    
