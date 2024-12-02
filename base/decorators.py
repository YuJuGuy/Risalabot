from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from .models import UserStoreLink

from functools import wraps

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
