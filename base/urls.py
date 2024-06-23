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
    
    path('authstore/', authview.authstore, name="authstore"),
    path('callback/', authview.callback, name="callback"),
    path('unlinkstore/<str:store_id>/', authview.unlinkstore, name="unlinkstore"),
    
    path('email/', views.email, name="email"),
    

    path('', views.home, name="home"),
]
