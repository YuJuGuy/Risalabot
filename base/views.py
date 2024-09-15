from django.shortcuts import render,redirect
import random
import string
from django.contrib.auth import authenticate
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.utils.timezone import make_aware
from . forms import CreateUserForm, UserEventForm, CampaignForm, GroupCreationForm
from . models import User, Store, UserStoreLink, UserEvent, EventType, Campaign
from django.http import JsonResponse
from automations.tasks import send_email_task
from . apis import get_customer_data, create_customer_group, delete_customer_group,group_campaign, get_customers_from_group
from django.utils.crypto import get_random_string


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

def generate_unique_session_id():
    """Generate a unique session_id for the user."""
    while True:
        session_id = get_random_string(length=32)
        if not User.objects.filter(session_id=session_id).exists():
            return session_id

def registerPage(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    form = CreateUserForm()

    if request.method == 'POST':
        form = CreateUserForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.username = user.username.lower()
            user.session_id = generate_unique_session_id()
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
def manage_event(request, event_id=None):
    try:
        store = UserStoreLink.objects.get(user=request.user).store
        events = UserEvent.objects.filter(store=store)
    except UserStoreLink.DoesNotExist:
        messages.error(request, 'No store linked. Please link a store first.')
        return redirect('dashboard')
    
    event = None
    if event_id:
        event = UserEvent.objects.get(id=event_id, store=UserStoreLink.objects.get(user=request.user).store)

    if request.method == 'POST':
        form = UserEventForm(request.POST, instance=event)
        if form.is_valid():
            event_type = form.cleaned_data['event_type']
            subcategory = form.cleaned_data['subcategory']
            
            if UserEvent.objects.filter(store=store, event_type=event_type, subcategory=subcategory).exclude(id=event_id).exists():
                messages.error(request, 'You have already created an event for this type and subcategory.')
            else:
                event = form.save(commit=False)
                event.store = store
                event.save()
                if event_id:
                    messages.success(request, 'Event updated successfully.')
                else:
                    messages.success(request, 'Event created successfully.')
            return redirect('events')
        else:
            messages.error(request, 'Error saving event. Please correct the form errors.')
    else:
        form = UserEventForm(instance=event)

    try:
        order_updated_event_type = EventType.objects.get(name='order.updated')
        order_updated_event_type_id = order_updated_event_type.id
    except EventType.DoesNotExist:
        order_updated_event_type_id = None

    context = {
        'events': events,
        'form': form,
        'event': event,
        'order_updated_event_type_id': order_updated_event_type_id,
    }
    return render(request, 'base/events.html', context)

@login_required(login_url='login')
def delete_event(request, event_id):
    event = UserEvent.objects.get(id=event_id, store=UserStoreLink.objects.get(user=request.user).store)
    event.delete()
    messages.success(request, 'Event deleted successfully.')
    return redirect('events')
    

def home(request):
    return render(request, 'base/home.html')


@login_required(login_url='login')
def campaign(request):
    try:
        store = UserStoreLink.objects.get(user=request.user).store
        campaigns = Campaign.objects.filter(store=store)
        store_groups_response = group_campaign(request.user)
        
        if not store_groups_response.get('success'):
            messages.error(request, 'Failed to fetch store groups.')
            return redirect('dashboard')
        
        store_groups = store_groups_response.get('data', [])

    except UserStoreLink.DoesNotExist:
        messages.error(request, 'No store linked. Please link a store first.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = CampaignForm(request.POST, store_groups=store_groups)
        if form.is_valid():
            msg = form.cleaned_data['msg']
            group_id = form.cleaned_data['customers_group']
            scheduled_time = form.cleaned_data['scheduled_time']
            if scheduled_time.tzinfo is None or scheduled_time.tzinfo.utcoffset(scheduled_time) is None:
                scheduled_time = make_aware(scheduled_time)
            
            customers_numbers = get_customers_from_group(request.user, group_id)
            
            if len(customers_numbers) == 0:
                messages.error(request, 'No customers in the selected group.')
                return redirect('campaigns')
            
            if len(customers_numbers) > store.subscription.messages_limit - store.message_count:
                messages.error(request, 'Insufficient message balance.')
                return redirect('campaigns')
            
            send_email_task.apply_async(eta=scheduled_time, args=[customers_numbers, msg, store.id])
            
            campaign = form.save(commit=False)
            campaign.store = store
            if 'schedule' in request.POST:
                campaign.status = 'Scheduled'
            campaign.save()
            return redirect('campaigns')  # Adjust the redirect as needed
    else:
        form = CampaignForm(store_groups=store_groups)
    
    context = {
        'campaigns': campaigns,
        'form': form,
    }
    
    return render(request, 'base/campaigns.html', context)

    
@login_required(login_url='login')
def campaign_delete(request, campaign_id):
    try:
        # Get the store linked to the logged-in user
        user_store = UserStoreLink.objects.get(user=request.user).store
        # Get the campaign belonging to the user's store
        campaign = Campaign.objects.get(id=campaign_id, store=user_store)
        # Delete the campaign
        campaign.delete()
        messages.success(request, 'Campaign deleted successfully.')
    except (Campaign.DoesNotExist, UserStoreLink.DoesNotExist):
        # If either the campaign or the user-store link does not exist
        messages.error(request, 'Campaign not found or you do not have permission to delete it.')
    
    # Redirect to the campaigns page after the operation
    return redirect('campaigns')
        



#Customer Views
@login_required(login_url='login')
def customers_view(request):
    try:
        store = UserStoreLink.objects.get(user=request.user).store
        
    except UserStoreLink.DoesNotExist:
        messages.error(request, 'No store linked. Please link a store first.')
        return redirect('dashboard')
    
    form = GroupCreationForm()
    if request.method == 'POST':
        form = GroupCreationForm(request.POST)
        
        if form.is_valid():
            group_name = form.cleaned_data['name']
            conditions = form.cleaned_data['conditions']
            response = create_customer_group(request.user, group_name, conditions)
            if response.get('success') == True:
                messages.success(request, 'Group created successfully.')
                return redirect('customers')
            else:
                messages.error(request, 'Error creating group. Please correct the form errors 1.')
                return redirect('customers')
        else:
            messages.error(request, 'Error creating group. Please correct the form errors 2.')
            return redirect('customers')
    
    context = {
        'form': form,
    }
    
    return render(request, 'base/customer_list.html',context)


@login_required(login_url='login')
def get_customers(request):
    try:
        customer_data = get_customer_data(request.user)
        
        if not customer_data['success']:
            return JsonResponse({'error': 'Failed to fetch customer data from API'}, status=500)

        customers_list = customer_data['customers']

        customers_data = [{
            'name': customer['name'],
            'email': customer['email'],
            'phone': customer['phone'],
            'location': customer['location'],
            'groups': customer['groups'],
            'updated_at': customer['updated_at'],
        } for customer in customers_list]

        return JsonResponse({
            'customers': customers_data,
            'group_counts': customer_data.get('group_counts', {}),
            'group_id_to_name': customer_data.get('group_id_to_name', {}),
            'total_count': len(customers_list),
        }, status=200)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

    
    
@login_required(login_url='login')
def delete_customer_list(request, group_id):
    response = delete_customer_group(request.user, group_id)
    if response.get('success'):
        messages.success(request, 'Group deleted successfully.')
        return redirect('customers')
    else:
        messages.error(request, 'Error deleting group.')
        return redirect('customers')
