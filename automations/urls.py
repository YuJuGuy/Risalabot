from django.urls import path
from . import views, channel_views

urlpatterns = [
    path('webhook', views.webhook, name='webhook'),
    path('link-whatsapp-channel/', channel_views.whatsapp_session, name="whatsapp_session"),
    path('create-whatsapp-session/', channel_views.create_whatsapp_session, name="create_whatsapp_session"),
    path('get-whatsapp-qr-code/', channel_views.get_whatsapp_qr_code, name='get_whatsapp_qr_code'),
    path('whatsapp-details/', channel_views.get_whatsapp_details, name='whatsapp_details'),
    path('stop-whatsapp/', channel_views.stop_whatsapp, name='whatsapp_stop'),
]


