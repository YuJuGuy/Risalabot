from django.shortcuts import render,redirect
from django.views import View
from django.http import HttpResponse



def home_view(request):
    return render(request, 'base/home.html')