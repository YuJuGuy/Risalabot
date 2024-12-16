from django.shortcuts import render
from django.http import HttpResponse
from base.models import User, Store, Subscription, UserStoreLink, StaticBotStart
from django.contrib.auth.decorators import login_required
from base.decorators import check_token_validity
from django.http import JsonResponse
from . forms import StaticBotStartForm
from django.urls import reverse
from . models import StaticBot, StaticBotStart
from django.views.decorators.http import require_http_methods
from . forms import StaticBotForm
from django.shortcuts import redirect
import json

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


    context.update({
        'botenabled': botenabled,
    })

    return render(request, 'base/staticbot.html', context)


@login_required(login_url='login')
def get_bot(request):
    # Fetch data for both StaticBotStart and StaticBots.
    try:
        # Fetch store data with related user and subscription
        store_link = UserStoreLink.objects.select_related('store').get(user=request.user)
        store = store_link.store


        # Fetch StaticBotStart
        bot_start = StaticBotStart.objects.filter(store=store).first()
        start_bot_data = {
            'enabled': bot_start.enabled if bot_start else False,
            'return_message': bot_start.return_message if bot_start else "",
            'hours': bot_start.hours if bot_start else 0,
        }

        # Fetch all StaticBots
        static_bots = StaticBot.objects.filter(store=store)
        static_bot_data = [{
            'id': bot.id,
            'message': bot.message,
            'return_message': bot.return_message,
            'condition': bot.condition,
            'condition_display': dict(StaticBot.CONDITION_CHOICES).get(bot.condition),
        } for bot in static_bots]

        return JsonResponse({
            'success': True,
            'start_bot': start_bot_data,
            'static_bots': static_bot_data
        }, status=200)

    except UserStoreLink.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'No store linked to your account.'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)



@login_required(login_url='login')
@require_http_methods(["POST"])
def start_static_bot_post(request):
    """Handle StaticBotStart POST logic."""
    try:
        # Fetch store
        store = UserStoreLink.objects.select_related('store').get(user=request.user).store
        form = StaticBotStartForm(request.POST)

        if form.is_valid():
            bot_start, _ = StaticBotStart.objects.get_or_create(store=store)
            bot_start.enabled = form.cleaned_data['enabled']
            bot_start.return_message = form.cleaned_data['return_message']
            bot_start.hours = form.cleaned_data['hours']
            bot_start.save()

            return JsonResponse({'success': True, 'type': 'success', 'message': 'تم تحديث البوت بنجاح'}, status=200)
        else:
            return JsonResponse({'success': False, 'type': 'error', 'errors': form.errors}, status=400)
    except UserStoreLink.DoesNotExist:
        return JsonResponse({'success': False, 'type': 'error', 'message': 'لا يوجد متجر مرتبط بالمستخدم'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'type': 'error', 'message': str(e)}, status=500)



@login_required(login_url='login')
@require_http_methods(["POST", "PUT"])
def static_bot_post(request):
    """Handle StaticBot POST (create) and PUT (update) logic."""
    try:
        # Fetch the store associated with the user
        store_link = UserStoreLink.objects.select_related('store').get(user=request.user)
        store = store_link.store  # Ensure we have the store instance

        if request.method == "PUT":
            # Parse PUT data from the request body
            try:
                data = json.loads(request.body)
            except json.JSONDecodeError:
                return JsonResponse({'success': False, 'message': 'Invalid JSON payload.'}, status=400)

            # Get bot ID
            bot_id = data.get("id")
            if not bot_id:
                return JsonResponse({'success': False, 'message': 'Missing bot ID for update.'}, status=400)

            # Fetch and update the bot
            static_bot = StaticBot.objects.filter(id=bot_id, store=store).first()
            if not static_bot:
                return JsonResponse({'success': False, 'message': 'لم يتم العثور على البوت'}, status=404)

            # Update fields
            static_bot.message = data.get("message", static_bot.message)
            static_bot.return_message = data.get("return_message", static_bot.return_message)
            static_bot.condition = data.get("condition", static_bot.condition)
            static_bot.save()

            return JsonResponse({'success': True, 'type':'success', 'message': 'تم تحديث البوت بنجاح', 'id': static_bot.id}, status=200)

        elif request.method == "POST":
            # Directly create a StaticBot instance
            data = request.POST
            message = data.get('message')
            return_message = data.get('return_message')
            condition = data.get('condition')

            if not message or not return_message or not condition:
                return JsonResponse({'success': False, 'type':'error', 'message': 'كل الحقول مطلوبة'}, status=400)

            # Create the StaticBot
            static_bot = StaticBot.objects.create(
                store=store,
                message=message,
                return_message=return_message,
                condition=int(condition)  # Ensure condition is an integer
            )

            return JsonResponse({'success': True, 'message': 'تم انشاء البوت بنجاح', 'type': 'success'}, status=201)

    except UserStoreLink.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'لا يوجد متجر مرتبط بالمستخدم'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@login_required(login_url='login')
def delete_static_bot(request, bot_id):
    try:
        store = UserStoreLink.objects.select_related('store').get(user=request.user).store
        static_bot = StaticBot.objects.get(id=bot_id, store=store)
        static_bot.delete()
        logger.info(f"Deleted bot with ID: {bot_id}")
        return JsonResponse({'success': True, 'type': 'success', 'message': 'تم حذف البوت بنجاح.', 'id': bot_id}, status=200)
    except StaticBot.DoesNotExist:
        logger.warning(f"StaticBot with ID {bot_id} not found.")
        return JsonResponse({'success': False, 'type': 'error', 'message': 'لم يتم العثور على البوت'}, status=404)




    









