from django.shortcuts import render,redirect
from django.contrib.auth import authenticate
from celery.exceptions import CeleryError
from django.contrib import messages
from django.db import transaction
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from . forms import CreateUserForm, GroupCreationForm
from . models import User, Store, UserStoreLink, Campaign, Flow, Customer, Group,ActivityLog
from django.http import JsonResponse
from . apis import get_customer_data, create_customer_group, delete_customer_group
from django.utils.crypto import get_random_string
from Risalabot.celery import app as celery_app
from django.db.models import Count
from . decorators import check_token_validity


import logging

logger = logging.getLogger(__name__)


__all__ = ('celery_app',) 



def home(request):
    return render(request, 'base/home.html')


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
            messages.error(request, 'هذا الحساب غير موجود.')

        user = authenticate(request, email=email, password=password)

        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, 'البريد الإلكتروني أو كلمة المرور غير متطابقة.')
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
        
        # Check if the email already exists
        email = form.data.get('email')
        if User.objects.filter(email=email).exists():
            messages.error(request, 'البريد الإلكتروني موجود بالفعل.')
        else:
            if form.is_valid():
                user = form.save(commit=False)
                user.username = user.username.lower()
                user.session_id = generate_unique_session_id()
                user.save()
                login(request, user)
                return redirect('dashboard')
            else:
                messages.error(request, 'حدث خطأ ما. يرجى التحقق من البيانات المدخلة.')

        # Check if passwords match
        password1 = form.data.get('password1')
        password2 = form.data.get('password2')
        if password1 and password2 and password1 != password2:
            messages.error(request, 'كلمات المرور غير متطابقة.')

    return render(request, 'base/login_register.html', {'form': form})


@login_required(login_url='login')
@check_token_validity
def dashboard(request, context=None):
    # Initialize default values
    if context is None:
        context = {}
    
    context.update({
        'store': None,
    })

    try:
        # Get store data if it exists
        store_link = UserStoreLink.objects.select_related('store').get(user=request.user)
        store = store_link.store

    except UserStoreLink.DoesNotExist:
        logger.error(f"No store linked to your account")
    except Exception as e:
        logger.error(f"Error in dashboard view: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)   
    return render(request, 'base/dashboard.html', context)


@login_required(login_url='login')
def get_dashboard_data(request):
    try:
        store = UserStoreLink.objects.get(user=request.user).store
        activity_log = ActivityLog.objects.filter(store=store)
        activity_log_data = []
        for log in activity_log:
            activity_log_data.append({
                'date': log.date,
                'count': log.count,
                'activity_type': log.get_activity_type_display(),
                'source_type': log.get_source_type_display(),
            })
        data = {
            'message_count': store.total_messages_sent,
            'purchases': store.total_purchases,
            'total_customers': store.total_customers,
            'clicks': store.total_clicks,
            'active_automations': Flow.objects.filter(owner=request.user, status='active').count() + Campaign.objects.filter(store=store, status='scheduled').count(),
            'activty_log': activity_log_data
        }
        return JsonResponse({'success': True, 'data': data}, status=200)
    except UserStoreLink.DoesNotExist:
       return JsonResponse({'success': False, 'type': 'info', 'message': 'No store linked. You won\'t be able to see any data without linking a store.'}, status=400)






#Customer Views

@login_required(login_url='login')
@check_token_validity
def customers_view(request, context=None):
    try:
        store = UserStoreLink.objects.get(user=request.user).store
    except UserStoreLink.DoesNotExist:
        messages.error(request, 'No store linked. Please link a store first.')
        return redirect('dashboard')

    if context is None:
        context = {}

    form = GroupCreationForm()
    if request.method == 'POST':
        form = GroupCreationForm(request.POST)

        if form.is_valid():
            group_name = form.cleaned_data['name']
            conditions = form.cleaned_data['conditions']
            response = create_customer_group(request.user, group_name, conditions)
            
            if response.get('success'):
                # Return a JSON response on successful creation
                return JsonResponse({'status': 'success', 'message': 'تم إنشاء المجموعة بنجاح.'}, status=200)
            else:
                # Return JSON with error messages
                error_message = response.get('error', {}).get('message', 'حدث خطأ ما.')
                error_fields = response.get('error', {}).get('fields', {})
                errors = {field: messages_list for field, messages_list in error_fields.items()}
                return JsonResponse({'status': 'error', 'message': error_message, 'errors': errors}, status=400)
        else:
            return JsonResponse({'status': 'error', 'message': 'فشل التحقق من صحة النموذج.'}, status=400)

    context.update({
        'form': form,
    })
    
    return render(request, 'base/customer_list.html', context)




@login_required(login_url='login')
def get_customers(request):
    try:
        # Get the store associated with the logged-in user
        store = UserStoreLink.objects.get(user=request.user).store

        # Retrieve customers for the specific store
        customers_list = Customer.objects.filter(store=store)

        # Prepare customer data
        customers_data = [{
            'name': customer.customer_name,
            'email': customer.customer_email,
            'phone': customer.customer_phone,
            'location': customer.customer_location,
            'groups': list(customer.customer_groups.values_list('name', flat=True)),  # Group IDs
            'updated_at': customer.customer_updated_at.strftime('%Y-%m-%d %H:%M')
        } for customer in customers_list]
        

        # Calculate group counts

        # Create a dictionary of group IDs to names
        group_data = (
            Group.objects.filter(store=store).exclude(name='ج��يع العملاء')
            .annotate(customer_count=Count('customers'))  # Count related customers for each group
            .values('group_id', 'name', customer_count=Count('customers'))  # Include group ID, name, and customer count

        )

        # Convert to list of dictionaries for easier JSON handling
        group_data_list = list(group_data)
        
        return JsonResponse({
            'customers': customers_data,
            'group_data': group_data_list,  # List of dictionaries with 'name' and 'customer_count'
            'total_count': len(customers_list),
        }, status=200)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)



@login_required(login_url='login')
@transaction.atomic
def sync_data(request):
    try:
        # Fetch the latest customer data from the API
        customer_data = get_customer_data(request.user)
        if not customer_data.get('success', False):
            logger.error("Failed to fetch customer data from API.")
            return JsonResponse({'error': 'فشل في جلب بيانات العملاء من واجهة برمجة التطبيقات'}, status=500)

        # Get the store associated with the logged-in user
        store = Store.objects.get(userstorelink__user=request.user)

        # Clear out existing customers for this store but keep groups intact
        Customer.objects.filter(store=store).delete()
        Group.objects.filter(store=store).delete()

        # Update or create groups based on the data received
        group_id_to_name = customer_data.get('group_id_to_name', {})
        for group_id, group_name in group_id_to_name.items():
            Group.objects.get_or_create(
                group_id=group_id,
                store=store,
                defaults={'name': group_name}  # Corrected to ensure it's a dictionary
            )

        # Add new customers and associate them with groups
        customers_list = customer_data['customers']
        for customer in customers_list:
    # Create the customer entry
            customer_obj = Customer.objects.create(
                store=store,
                customer_name=customer['name'],
                customer_email=customer['email'],
                customer_phone=customer['phone'],
                customer_location=customer['location'],
                customer_updated_at=customer['updated_at'],
            )

            # Debug print: check group IDs for the customer
            group_ids = customer.get('groups', [])

            # Associate the customer with groups
            groups = Group.objects.filter(group_id__in=group_ids, store=store)
            customer_obj.customer_groups.set(groups)

        return JsonResponse({'status': 'success', 'message': 'تم تحديث قاعدة البيانات بنجاح.'}, status=200)

    except Exception as e:
        logger.error("Error during sync: %s", e, exc_info=True)
        return JsonResponse({'error': 'حدث خطأ أثناء المزامنة.'}, status=500)

    
    
@login_required(login_url='login')
def delete_customer_list(request, group_id):
    if request.method == "POST":
        response = delete_customer_group(request.user, group_id)
        if response.get('success'):
            return JsonResponse({'status': 'success', 'message': 'تم حذف المجموعة بنجاح.'})
        else:
            return JsonResponse({'status': 'error', 'message': 'فشل حذف المجموعة.'}, status=400)
    return JsonResponse({'status': 'error', 'message': 'طريقة الطلب غير صالحة.'}, status=405)

