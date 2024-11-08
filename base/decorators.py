from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from .models import UserStoreLink

def check_token_validity(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        context = kwargs.get('context', {})
        if request.user.is_authenticated:
            user_store_link = UserStoreLink.objects.filter(user=request.user).first()
            if user_store_link and not user_store_link.store.token_valid:
                context.update({
                    'token_invalid': True,
                    'token_message': "Your store connection has expired. Please reconnect your store to continue using our services."
                })
        # Pass context explicitly to the response
        response = view_func(request, *args, context=context, **kwargs)
        return response
    return _wrapped_view