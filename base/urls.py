from django.urls import path
from . import authenticate_user
from . import authenticate_store
from . import flows
from . import campaigns
from . import customers
from . import home
from . import dashboard
from . import channel_views
from .Utils import data_utils
from . import staticbot
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('login/', authenticate_user.loginPage, name="login"),
    path('logout/', authenticate_user.logoutUser, name="logout"),
    path('register/', authenticate_user.registerPage, name="register"),
    path('sync_data/', data_utils.sync_data, name='sync_data'),
    path('clear_notifications/',data_utils.clear_notifications, name='clear_notifications'),

    path('reset_password/', auth_views.PasswordResetView.as_view(
             subject_template_name='registration/password_reset_subject.txt',
             email_template_name='registration/password_reset_email.txt',
             template_name="base/reset_password.html"
         ), name="reset_password"),

    path('reset_password_sent/', auth_views.PasswordResetDoneView.as_view(template_name="base/reset_password_sent.html"), name="password_reset_done"),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name="base/password_reset_confirm.html"), name="password_reset_confirm"),
    path('reset_password_complete/', auth_views.PasswordResetCompleteView.as_view(template_name="base/password_reset_complete.html"), name="password_reset_complete"),
    
    
    path('dashboard/', dashboard.dashboard_view, name="dashboard"),
    path('get-dashboard-data/', dashboard.get_dashboard_data, name='get_dashboard_data'),
    
    
    path('flows/', flows.flows, name='flows'),
    path('flow/<uuid:flow_id>/', flows.flow_builder, name='flow'),
    path('delete-flow/<uuid:flow_id>/', flows.delete_flow, name='delete_flow'),
    path('get-flows/', flows.get_flows, name='get_flows'),
    path('activate-suggested-flow/<int:suggestion_id>/', flows.activate_suggested_flow, name='activate_suggested_flow'),


    
    path('campaigns/', campaigns.campaign, name='campaigns'),
    path('cancel-campaign/<uuid:campaign_id>/', campaigns.campaign_cancel, name='campaign_cancel'),
    path('delete-campaign/<uuid:campaign_id>/', campaigns.delete_campaign, name='campaign_delete'),
    path('edit_campaign/<uuid:campaign_id>/', campaigns.edit_campaign, name='edit_campaign'),
    path('get_campaigns/', campaigns.get_campaign_data, name='get_campaigns'),
    path('get_campaigns/<uuid:campaign_id>/', campaigns.get_campaign_data, name='get_campaigns'),

    
    
    path('customers/', customers.customers_view, name='customers'),
    path('get-customers/', customers.get_customers, name='get_customers'),
    path('delete-group/<int:group_id>/', customers.delete_customer_list, name='delete_group'),
    
    path('authstore/', authenticate_store.authstore, name="authstore"),
    path('callback/', authenticate_store.callback, name="callback"),
    path('unlinkstore/<str:store_id>/', authenticate_store.unlinkstore, name="unlinkstore"),
    
    path('channel/', channel_views.whatsapp_session, name="whatsapp_session"),
    path('create-whatsapp-session/', channel_views.create_whatsapp_session, name="create_whatsapp_session"),
    path('get-whatsapp-qr-code/', channel_views.get_whatsapp_qr_code, name='get_whatsapp_qr_code'),
    path('whatsapp-details/', channel_views.get_whatsapp_details, name='whatsapp_details'),
    path('stop-whatsapp/', channel_views.stop_whatsapp, name='whatsapp_stop'),

    path('bot/', staticbot.bot, name='static_bot'),
    path('get-bots/', staticbot.get_bot, name='get_bots'),
    path('startbot/', staticbot.start_static_bot_post, name='startbot'),
    path('staticbot/', staticbot.static_bot_post, name='staticbot'),
    path('toggle-botenabled/', staticbot.toggle_bot_enabled, name='toggle_bot_enabled'),
    path('delete-bot/<int:bot_id>/', staticbot.delete_static_bot, name='delete_bot'),

    path('', home.home_view, name="home"),
]
