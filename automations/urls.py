from django.urls import path
from . import webhooks
from . import whatsapp_webhook
from . import facebook_webhooks

urlpatterns = [
    path('webhook', webhooks.webhook, name='webhook'),
    path('fbwebhook', facebook_webhooks.webhook, name='fbwebhook'),
    path('whatsapp', whatsapp_webhook.whatsapp_hook, name='whatsapp_hook'),

]


