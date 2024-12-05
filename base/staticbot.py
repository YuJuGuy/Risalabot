from django.shortcuts import render
from django.http import HttpResponse
from base.models import User, Store, Subscription, UserStoreLink, StaticBotStart
from django.contrib.auth.decorators import login_required
from base.decorators import check_token_validity
from django.http import JsonResponse
from . forms import StaticBotStartForm
from django.urls import reverse

import logging

logger = logging.getLogger(__name__)

@login_required(login_url='login')
@check_token_validity
def bot(request, context=None):
    if context is None:
        context = {}

    try:
        # Get store data if it exists
        store_link = UserStoreLink.objects.select_related('store').get(user=request.user)
        store = store_link.store
        subscription = Subscription.objects.get(store=store)
        botenabled = subscription.staticbot

    except UserStoreLink.DoesNotExist:
        logger.error(f"No store linked to your account")
        return redirect('dashboard')
    # if subscription is blank
    except Subscription.DoesNotExist:
        botenabled = False
    except Exception as e:
        logger.error(f"Error in dashboard view: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

    if request.method == 'POST':
        form = StaticBotStartForm(request.POST)
        if form.is_valid():

            # Save the form data to the database
            staticbotstart = StaticBotStart.objects.get_or_create(store=UserStoreLink.objects.get(user=request.user).store)[0]
            staticbotstart.enabled = form.cleaned_data['enabled']
            staticbotstart.condition = form.cleaned_data['condition']
            staticbotstart.message = form.cleaned_data['message']
            staticbotstart.hours = form.cleaned_data['hours']
            staticbotstart.save()
            return JsonResponse(
                {'success': True, 'message': 'تم إنشاء البوت وتم حفظه بنجاح.', 'type': 'success'}, 
                status=200
            )
        else:
            error_messages = form.get_custom_errors()
            return JsonResponse({'success': False, 'message': error_messages, 'type': 'error'}, status=400)

    else:
        # Fetch existing data to prepopulate the form
        try:
            existing_data = StaticBotStart.objects.get(store=UserStoreLink.objects.get(user=request.user).store)
            form = StaticBotStartForm(initial={
                'enabled': existing_data.enabled,
                'condition': existing_data.condition,
                'message': existing_data.message,
                'hours': existing_data.hours

                # Add more fields as needed
            })
        except StaticBotStart.DoesNotExist:
            form = StaticBotStartForm()

    context.update({
        'botenabled': botenabled,
        'form': form
    })

    return render(request, 'base/staticbot.html', context)