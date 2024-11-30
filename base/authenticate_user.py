from django.shortcuts import render,redirect
from django.contrib.auth import authenticate
from celery.exceptions import CeleryError
from django.contrib import messages
from django.db import transaction
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from . models import User, Store, UserStoreLink, Campaign, Flow, Customer, Group,ActivityLog
from django.http import JsonResponse
from django.utils.crypto import get_random_string
from Risalabot.celery import app as celery_app
from . decorators import check_token_validity

from datetime import datetime

import logging
logger = logging.getLogger(__name__)


__all__ = ('celery_app',) 








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
    return redirect('home')

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

        return JsonResponse({'status': 'success', 'type': 'success', 'message': 'تم تحديث قاعدة البيانات بنجاح.'}, status=200)

    except Exception as e:
        logger.error("Error during sync: %s", e, exc_info=True)
        return JsonResponse({'status': 'error', 'type': 'error', 'message': 'حدث خطأ أثناء المزامنة.'}, status=500)

    
    
