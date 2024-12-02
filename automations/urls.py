from django.urls import path

from . import webhooks

urlpatterns = [
    path('webhook', webhooks.webhook, name='webhook'),
    path('whatsapp', webhooks.whatsapp_hook, name='whatsapp_hook'),

]


