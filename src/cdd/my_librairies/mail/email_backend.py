from django.core.mail.backends.smtp import EmailBackend
from django.core.mail.utils import DNS_NAME
from django.core.mail import get_connection
import ssl

class MyCustomEmailBackend(EmailBackend):
    def open(self):
        if self.connection:
            return False

        connection_params = {'local_hostname': DNS_NAME.get_fqdn()}
        if self.timeout is not None:
            connection_params['timeout'] = self.timeout
        if self.use_ssl:
            connection_params.update({
                'keyfile': self.ssl_keyfile,
                'certfile': self.ssl_certfile,
            })
        try:
            self.connection = self.connection_class(
                self.host, self.port, **connection_params
            )
            
            if self.use_tls:
                context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
                
                if self.ssl_certfile and self.ssl_keyfile:
                    context.load_cert_chain(certfile=self.ssl_certfile, keyfile=self.ssl_keyfile)
                self.connection.starttls(context=context)
            self.connection.login(self.username, self.password)
            return True
        except OSError:
            if not self.fail_silently:
                raise