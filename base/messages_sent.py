from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .decorators import check_token_validity
from base.models import UserStoreLink, Notification, MessagesSent, Store, User
from django.contrib import messages
from django.http import JsonResponse
from django.utils.crypto import get_random_string
from django.utils import timezone
from base.Utils.cache_utils import get_messages_sent
import logging

logger = logging.getLogger(__name__)



@login_required(login_url='login')
@check_token_validity
def messages_view(request, context=None):
    # Use the context passed from the decorator (don't re-initialize it)
    if context is None:
        context = {}

    try:
        # Try to fetch the store linked to the user
        store = UserStoreLink.objects.get(user=request.user).store
        context['store'] = store  # Add store to context
        context['notification_count'] = Notification.objects.filter(store=store).count()
        context['notifications'] = Notification.objects.filter(store=store).order_by('-created_at')
    except UserStoreLink.DoesNotExist:
        logger.error(f"No store linked to user {request.user.id}")
        return redirect('dashboard')  # Redirect to dashboard if no store linked

    # Continue with rendering the template if the store exists
    return render(request, 'base/messages.html', context)

@login_required(login_url='login')
def get_messages(request):
    store = UserStoreLink.objects.select_related('store').get(user=request.user).store
    
    # Optimize query for messages by selecting related fields
    messages = get_messages_sent(store)

    return JsonResponse({'messages': messages})
