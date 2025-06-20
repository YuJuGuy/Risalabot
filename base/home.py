from django.shortcuts import render,redirect
from django.views import View
from django.http import HttpResponse



def home_view(request):
    return redirect('dashboard')


def privacy_view(request):
    return render(request, 'base/privacy.html')

def faq_view(request):
    return render(request, 'base/faq.html')

