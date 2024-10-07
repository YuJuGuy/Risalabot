from django.urls import path
from . import views
from . import authview
from django.contrib.auth import views as auth_views
urlpatterns = [
    path('login/', views.loginPage, name="login"),
    path('logout/', views.logoutUser, name="logout"),
    path('register/', views.registerPage, name="register"),

    path('reset_password/', auth_views.PasswordResetView.as_view(), name="reset_password"),
    path('reset_password_sent/', auth_views.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path('reset_password_complete/', auth_views.PasswordResetCompleteView.as_view(), name="password_reset_complete"),
    
    
    path('dashboard/', views.dashboard, name="dashboard"),
    
    path('events/', views.manage_event, name='events'),
    path('events/<int:event_id>/', views.manage_event, name='manage_event'),
    path('events/delete/<int:event_id>/', views.delete_event, name='delete_event'),
    
    
    path('flows/', views.flows, name='flows'),
    path('flow/<uuid:flow_id>/', views.flow_builder, name='flow'),
    path('flow/delete/<int:event_id>/', views.delete_flow, name='delete_flow'),
    path('activate-suggested-flow/<int:suggestion_id>/', views.activate_suggested_flow, name='activate_suggested_flow'),


    
    path('campaigns/', views.campaign, name='campaigns'),
    path('cancel-campaign/<int:campaign_id>/', views.campaign_cancel, name='campaign_cancel'),
    path('delete-campaign/<int:campaign_id>/', views.delete_campaign, name='campaign_delete'),
    path('edit_campaign/<int:campaign_id>/', views.edit_campaign, name='edit_campaign'),
    path('get_campaigns/', views.get_campaign_data, name='get_campaigns'),
    path('get_campaigns/<int:campaign_id>/', views.get_campaign_data, name='get_campaigns'),

    
    
    path('customers/', views.customers_view, name='customers'),
    path('get-customers/', views.get_customers, name='get_customers'),
    path('delete-group/<int:group_id>/', views.delete_customer_list, name='delete_group'),
    
    path('authstore/', authview.authstore, name="authstore"),
    path('callback/', authview.callback, name="callback"),
    path('unlinkstore/<str:store_id>/', authview.unlinkstore, name="unlinkstore"),
    
    

    

    path('', views.home, name="home"),
]
