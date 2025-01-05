from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from .models import UserStoreLink
from django.core.cache import cache
from datetime import datetime, timedelta
from functools import wraps
from django.http import JsonResponse

def check_token_validity(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        context = kwargs.get('context', {})
        
        if request.user.is_authenticated:
            try:
                # Query to find the UserStoreLink
                user_store_link = UserStoreLink.objects.get(user=request.user)
                
                # Check if the store exists and the token is valid
                if user_store_link.store and not user_store_link.store.token_valid:
                    context.update({
                        'token_invalid': True,
                        'token_message': "لقد انتهت صلاحية اتصال متجرك. يرجى إعادة الاتصال بمتجرك للاستمرار في استخدام خدماتنا."
                    })
                    return view_func(request, *args, context=context, **kwargs)

            except UserStoreLink.DoesNotExist:
                print("UserStoreLink does not exist")
                # Catch the exception and handle the case where the link does not exist
                context.update({
                    'token_invalid': True,
                    'token_message': "لم يتم ربط المتجر. يرجى ربط متجر أولا."
                })
                return view_func(request, *args, context=context, **kwargs)

        # Continue processing the view if no issues
        return view_func(request, *args, context=context, **kwargs)

    return _wrapped_view


def rate_limit(key_prefix, limit=5, period=60):
    """
    Rate limiting decorator that allows `limit` requests per `period` seconds
    
    Args:
        key_prefix (str): Prefix for the cache key
        limit (int): Number of allowed requests per period
        period (int): Time period in seconds
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            # Create a unique cache key for this user and endpoint
            cache_key = f"rate_limit:{key_prefix}:{request.user.id}"
            
            # Get the current requests list from cache
            requests = cache.get(cache_key, [])
            now = datetime.now()
            
            # Remove requests older than the period
            requests = [req for req in requests 
                       if req > now - timedelta(seconds=period)]
            
            # Check if rate limit is exceeded
            if len(requests) >= limit:
                return JsonResponse({
                    'success': False,
                    'type': 'error',
                    'message': 'تم تجاوز حدود الطلبات. يرجى المحاولة لاحقا بعد دقيقة.'
                }, status=429)
            
            # Add current request timestamp
            requests.append(now)
            
            # Store updated requests list with TTL
            cache.set(cache_key, requests, period)
            
            # Execute the view
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator