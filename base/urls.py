from django.urls import path
from . import views
from . import authview

urlpatterns = [
    path('login/', views.loginPage, name="login"),
    path('logout/', views.logoutUser, name="logout"),
    path('register/', views.registerPage, name="register"),

    path('dashboard/', views.dashboard, name="dashboard"),
    
    path('authstore/', authview.authstore, name="authstore"),
    path('callback/', authview.callback, name="callback"),
    

    path('', views.home, name="home"),
]
