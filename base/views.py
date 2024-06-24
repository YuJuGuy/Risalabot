from django.shortcuts import render,redirect, get_object_or_404
from django.contrib.auth import authenticate
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from . forms import CreateUserForm, UserEventForm
from . models import User, Store, UserStoreLink, UserEvent, EventType
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

@login_required(login_url='login')
def events(request):
    try:
        store = UserStoreLink.objects.get(user=request.user).store
        events = UserEvent.objects.filter(store=store)
    except UserStoreLink.DoesNotExist:
        messages.error(request, 'No store linked. Please link a store first.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = UserEventForm(request.POST)
        if form.is_valid():
            event_type = form.cleaned_data['event_type']
            subcategory = form.cleaned_data['subcategory']
            
            # Check if an event with the same event_type already exists for the user
            if UserEvent.objects.filter(store=store, event_type=event_type).exists():
                messages.error(request, 'You have already created an event for this type.')
            else:
                event = form.save(commit=False)
                event.store = store
                event.save()
                messages.success(request, 'Event created successfully.')
            return redirect('events')
        else:
            messages.error(request, 'Error creating event. Please correct the form errors.')
    else:
        form = UserEventForm()

    try:
        order_updated_event_type = EventType.objects.get(name='order.updated')
        order_updated_event_type_id = order_updated_event_type.id
    except EventType.DoesNotExist:
        order_updated_event_type_id = None  # Handle if event type doesn't exist

    context = {
        'events': events,
        'form': form,
        'order_updated_event_type_id': order_updated_event_type_id,
    }
    return render(request, 'base/events.html', context)

@login_required(login_url='login')
def edit_event(request, event_id):
    event = get_object_or_404(UserEvent, id=event_id, store__userstorelink__user=request.user)
    if request.method == 'POST':
        form = UserEventForm(request.POST, instance=event)
        if form.is_valid():
            form.save()
            messages.success(request, 'Event updated successfully.')
            return redirect('events')
        else:
            messages.error(request, 'Error updating event. Please correct the form errors.')
    else:
        form = UserEventForm(instance=event)  # Pass the instance of UserEvent to prepopulate the form

    context = {
        'form': form,
        'event': event
    }
    return render(request, 'base/edit_event.html', context)

@login_required(login_url='login')
def delete_event(request, event_id):
    event = get_object_or_404(UserEvent, id=event_id, store__userstorelink__user=request.user)
    event.delete()
    messages.success(request, 'Event deleted successfully.')
    return redirect('events')
    

def home(request):
    return render(request, 'base/home.html')




def email(request):
    send_email_task.delay()
    return HttpResponse('<h1>Email Sent</h1>')
    