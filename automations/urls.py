from django.urls import path
from . import views, channel_views

urlpatterns = [
    path('webhook', views.webhook, name='webhook'),
    path('link-channel/', channel_views.create_whatsapp_session, name="whatsapp_session"),
    path('get_channel_qr_code/', channel_views.get_whatsapp_qr_code, name='get_whatsapp_qr_code'),
    path('channel_details/', channel_views.get_whatsapp_details, name='whatsapp_details'),
    path('channel_stop/', channel_views.stop_whatsapp, name='whatsapp_stop'),
]


