from django.shortcuts import render
from django.shortcuts import render
def home(request):
    return render(request, 'home.html')

def rooms(request):
    return render(request,'rooms.html')