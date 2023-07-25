from django.conf import settings
from twilio.rest import Client

TWILIO_ACCOUNT_SID = settings.TWILIO_ACCOUNT_SID
TWILIO_AUTH_TOKEN = settings.TWILIO_AUTH_TOKEN
TWILIO_FROM_NUMBER = settings.TWILIO_FROM_NUMBER


client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)#, region=region)

def send_sms(to, from_=TWILIO_FROM_NUMBER, body=None):
    client.messages.create(
        to=to,
        from_=from_,
        body=body
    )
