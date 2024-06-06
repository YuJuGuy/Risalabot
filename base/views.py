from django.shortcuts import render,redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm


def loginPage(request):
    page = 'login'
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        username = request.POST.get('username').lower()
        password = request.POST.get('password')

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            messages.error(request, 'User does not exist')
            return render(request, 'base/login_register.html', {'page': page})

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, 'Username OR password does not exist')

    context = {'page': page}
    return render(request, 'base/login_register.html', context)

def logoutUser(request):
    logout(request)
    return redirect('login')

def registerPage(request):
    form = UserCreationForm()
    
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            username = form.cleaned_data.get('username').lower()
            user.username = username
            user.save()
            login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, 'An error has occurred during registration')
            
    return render(request, 'base/login_register.html', {'form': form})


@login_required(login_url='login')
def dashboard(request):
    return render(request, 'base/dashboard.html')

def home(request):
    return render(request, 'base/home.html')

