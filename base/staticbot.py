from django.shortcuts import render
from django.http import HttpResponse
from base.models import User, Store, Subscription, UserStoreLink
from django.contrib.auth.decorators import login_required
from base.decorators import check_token_validity
from django.http import JsonResponse

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
    #if subscrption is blank
    except Subscription.DoesNotExist:
        botenabled = False
    except Exception as e:
        logger.error(f"Error in dashboard view: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)



    context.update({
        'botenabled': botenabled,
    })

    return render(request, 'base/staticbot.html', context)