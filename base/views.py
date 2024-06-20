from django.shortcuts import render,redirect
from django.contrib.auth import authenticate
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from . forms import CreateUserForm
from . models import User, Store, UserStoreLink, UserEvent
from django.http import HttpResponse
from automations.tasks import sleepy, send_email_task

def loginPage(request):
    page = 'login'
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        email = request.POST.get('email').lower()
        password = request.POST.get('password')

        try:
            user = User.objects.get(email=email)
        except:
            messages.error(request, 'User does not exist')

        user = authenticate(request, email=email, password=password)

        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, 'Email OR password does not exit')

    context = {'page': page}
    return render(request, 'base/login_register.html', context)

def logoutUser(request):
    logout(request)
    return redirect('login')

def registerPage(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = CreateUserForm()

    if request.method == 'POST':
        form = CreateUserForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.username = user.username.lower()
            user.save()
            login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, 'An error occurred during registration')

    return render(request, 'base/login_register.html', {'form': form})


@login_required(login_url='login')
def dashboard(request):
    user_linked = UserStoreLink.objects.filter(user=request.user).exists()
    store = None
    message_count = 0
    if user_linked:
        store_link = UserStoreLink.objects.get(user=request.user)
        store = store_link.store
        message_count = store.message_count


    context = {
        'user_linked': user_linked,
        'store': store,
        'message_count': message_count
    }

    return render(request, 'base/dashboard.html', context)

def home(request):
    return render(request, 'base/home.html')


@login_required(login_url='login')
def automations(request):
    # Ensure the user is linked to at least one store
    user_store_link = UserStoreLink.objects.filter(user=request.user).first()
    if not user_store_link:
        messages.error(request, "You are not connected to any store.")
        return redirect('dashboard')

    store = user_store_link.store

    # Fetch or create the UserEvent for the store
    user_event, created = UserEvent.objects.get_or_create(store=store)

    if request.method == 'POST':
        user_event.abandoned_cart = request.POST.get('abandoned_cart', user_event.abandoned_cart)
        user_event.order_received = request.POST.get('order_received', user_event.order_received)
        user_event.order_cancelled = request.POST.get('order_cancelled', user_event.order_cancelled)
        user_event.order_updated = request.POST.get('order_updated', user_event.order_updated)
        user_event.shipment_updated = request.POST.get('shipment_updated', user_event.shipment_updated)
        user_event.save()
        
        messages.success(request, 'Automations updated successfully')
        return redirect('automations')  # Redirect to avoid re-submitting the form on refresh

    context = {
        'store': store,
        'abandoned_cart': user_event.abandoned_cart,
        'order_received': user_event.order_received,
        'order_cancelled': user_event.order_cancelled,
        'order_updated': user_event.order_updated,
        'shipment_updated': user_event.shipment_updated
    }
    
    return render(request, 'base/automations.html', context)

def email(request):
    send_email_task.delay()
    return HttpResponse('<h1>Email Sent</h1>')
    