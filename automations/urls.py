from django.urls import path
from . import webhooks
from . import whatsapp_webhook

urlpatterns = [
    path('webhook', webhooks.webhook, name='webhook'),
    path('whatsapp', whatsapp_webhook.whatsapp_hook, name='whatsapp_hook'),

]


