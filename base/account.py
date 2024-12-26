from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .decorators import check_token_validity
from base.models import UserStoreLink, Store, User, Notification
from django.contrib import messages
from django.http import JsonResponse
from django.utils.crypto import get_random_string
from django.contrib.auth import login
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


@login_required(login_url='login')
@check_token_validity
def account_view(request, context=None):
    # Ensure context is properly passed and not overwritten
    if context is None:
        context = {}

    # Initialize default values for context
    context.update({
        'store': None,  # Default store is None
        'notifications': None,  # Initialize notifications
        'notification_count': 0  # Initialize notification count
    })

    try:
        # Try to fetch the store linked to the user
        store_link = UserStoreLink.objects.select_related('store').get(user=request.user)
        store = store_link.store
        
        # Add the store to the context for use in the template


        context['store'] = store
        context['notification_count'] = Notification.objects.filter(store=store).count()
        context['notifications'] = Notification.objects.filter(store=store).order_by('-created_at')


    except UserStoreLink.DoesNotExist:
        logger.error(f"No store linked to user {request.user.id}")
        context.update({
            'error_message': "لم يتم ربط المتجر بحسابك. يرجى ربط المتجر أولا."
        })
        return render(request, 'base/dashboard.html', context)



    return render(request, 'base/account.html', context)

@login_required(login_url='login')
def change_password(request):
    if request.method == 'POST':
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        if not password1 or not password2:
            return JsonResponse({'success': False, 'type': 'error', 'message': 'يرجى إدخال كلمة المرور.'}, status=400)
        user = request.user
        if password1 == password2:
            user.set_password(password1)
            user.save()
            login(request, user)
            return JsonResponse({'success': True, 'type': 'success', 'message': 'تم تغيير كلمة المرور بنجاح.'}, status=200)
        else:
            return JsonResponse({'success': False, 'type': 'error', 'message': 'كلمات المرور غير متطابقة.'}, status=400)
    else:
        return JsonResponse({'success': False, 'type': 'error', 'message': 'المتجر غير مشترك بالخدمة.'}, status=400)
