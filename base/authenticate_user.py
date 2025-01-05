import re
from django.shortcuts import render,redirect
from django.contrib.auth import authenticate
from celery.exceptions import CeleryError
from django.contrib import messages
from django.db import transaction
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from . models import User, Store, UserStoreLink, Campaign, Flow, Customer, Group,ActivityLog
from django.http import JsonResponse
from . forms import CreateUserForm
from django.utils.crypto import get_random_string
from Risalabot.celery import app as celery_app
from . apis import get_customer_data
from . decorators import check_token_validity
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password

from datetime import datetime

import logging
logger = logging.getLogger(__name__)


__all__ = ('celery_app',) 









def loginPage(request):
    page = 'login'

    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        email = request.POST.get('email', '').lower()
        password = request.POST.get('password', '')
        errors = {}

        if not email:
            return JsonResponse({'success': False, 'type': 'error', 'message': 'يرجى إدخال البريد الإلكتروني.'})
        if not password:
            return JsonResponse({'success': False, 'type': 'error', 'message': 'يرجى إدخال كلمة المرور.'})

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
           return JsonResponse({'success': False, 'type': 'error', 'message': 'لا يوجد مستخدم بهذا البريد الإلكتروني.'})

        user = authenticate(request, email=email, password=password)

        if not errors and user is None:
            return JsonResponse({'success': False, 'type': 'error', 'message': 'البريد الإلكتروني او كلمة المرور غير صحيحة.'})

        if not errors:
            login(request, user)
            return JsonResponse({'success': True, 'redirect_url': '/dashboard'})
        else:
            return JsonResponse({'success': False, 'errors': errors})
    
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
        errors = {}

        # Extract email and passwords from the form
        email = form.data.get('email')
        password1 = form.data.get('password1')
        password2 = form.data.get('password2')

        # Check for email duplication
        if User.objects.filter(email=email).exists():
            return JsonResponse({
                'success': False,
                'type': 'error',
                'message': 'البريد الإلكتروني مستخدم بالفعل. يرجى استخدام بريد إلكتروني جديد.'
            })

        # Check if passwords match 
        if password1 and password2 and password1 != password2:
            return JsonResponse({
                'success': False,
                'type': 'error',
                'message': 'كلمات المرور غير متطابقة.'
            })

        # Validate password strength using Django's password validators
        try:
            validate_password(password1)
        except ValidationError as e:
            return JsonResponse({
                'success': False,
                'type': 'error',
                'message': 'كلمة المرور ضعيفة: ' + ' '.join(e.messages)
            })

        # Check if form is valid
        if form.is_valid():
            user = form.save(commit=False)
            user.username = user.username.lower()
            user.session_id = generate_unique_session_id()  # Ensure this function exists
            user.save()
            login(request, user)
            return JsonResponse({'success': True, 'redirect_url': '/dashboard'})
        else:
            # Collect form errors
            #log the for error
            logger.error(f"Form errors: {form.errors}")
            error_message = "حدث خطأ ما. يرجى التحقق من البيانات المدخلة."
            return JsonResponse({
                'success': False,
                'type': 'error',
                'message': error_message
            })

    # For GET requests
    return render(request, 'base/login_register.html', {'form': form})




    
    
