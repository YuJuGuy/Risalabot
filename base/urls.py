from django.urls import path
from . import views
from . import authview
from django.contrib.auth import views as auth_views
urlpatterns = [
    path('login/', views.loginPage, name="login"),
    path('logout/', views.logoutUser, name="logout"),
    path('register/', views.registerPage, name="register"),

    path('reset_password/', auth_views.PasswordResetView.as_view(template_name="base/reset_password.html"), name="reset_password"),
    path('reset_password_sent/', auth_views.PasswordResetDoneView.as_view(template_name="base/reset_password_sent.html"), name="password_reset_done"),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name="base/password_reset_confirm.html"), name="password_reset_confirm"),
    path('reset_password_complete/', auth_views.PasswordResetCompleteView.as_view(template_name="base/password_reset_complete.html"), name="password_reset_complete"),
    
    
    path('dashboard/', views.dashboard, name="dashboard"),
    
    
    
    path('flows/', views.flows, name='flows'),
    path('flow/<uuid:flow_id>/', views.flow_builder, name='flow'),
    path('delete-flow/<uuid:flow_id>/', views.delete_flow, name='delete_flow'),
    path('get-flows/', views.get_flows, name='get_flows'),
    path('activate-suggested-flow/<int:suggestion_id>/', views.activate_suggested_flow, name='activate_suggested_flow'),


    
    path('campaigns/', views.campaign, name='campaigns'),
    path('cancel-campaign/<uuid:campaign_id>/', views.campaign_cancel, name='campaign_cancel'),
    path('delete-campaign/<uuid:campaign_id>/', views.delete_campaign, name='campaign_delete'),
    path('edit_campaign/<uuid:campaign_id>/', views.edit_campaign, name='edit_campaign'),
    path('get_campaigns/', views.get_campaign_data, name='get_campaigns'),
    path('get_campaigns/<uuid:campaign_id>/', views.get_campaign_data, name='get_campaigns'),

    
    
    path('customers/', views.customers_view, name='customers'),
    path('get-customers/', views.get_customers, name='get_customers'),
    path('delete-group/<int:group_id>/', views.delete_customer_list, name='delete_group'),
    path('sync_data/', views.sync_data, name='sync_data'),
    
    path('authstore/', authview.authstore, name="authstore"),
    path('callback/', authview.callback, name="callback"),
    path('unlinkstore/<str:store_id>/', authview.unlinkstore, name="unlinkstore"),
    
    

    

    path('', views.home, name="home"),
]
