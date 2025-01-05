from math import log
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from . import admin_messages
import json
from base.models import User, Store, UserStoreLink, StaticBot, StaticBotStart, StaticBotLog, StaticBotMessage, StaticBotStartMessage, Notification
import logging
from automations.whatsapp_api import send_whatsapp_message, stop_session
from datetime import timedelta
from django.core.cache import cache
from datetime import datetime
from django.utils.timezone import now
from django.http import HttpResponseForbidden
from django.conf import settings
from base.Utils.cache_utils import get_store_by_id, get_user_by_store_id, get_user_store_link, get_recent_log, get_staticbot_start, get_staticbots, get_session, get_subscription


logger = logging.getLogger(__name__)


def stop_or_store_session(session_id, user=None):
    # Fetch the session data from cache
    data = cache.get(session_id)
    
    # If data is not found in cache, store it with current time and set a 3-minute expiration
    if not data:
        # Store session with the current time and optional user
        cache.set(session_id, {'time': datetime.now(), 'user': user}, 180)
        logger.info(f"Session {session_id} stored with user: {user}.")
        return

    # Check if the session's data is older than 2 minutes
    session_time = data.get('time')
    if session_time:
        if datetime.now() - session_time > timedelta(seconds=180):
            # Ensure that 'user' exists before calling stop_session
            user = data.get('user')
            if user:
                stop_session(user)
                logger.info(f"Session {session_id} is older than 2 minutes, so it was stopped.")
            else:
                logger.warning(f"Session {session_id} has no user associated, cannot stop.")
        else:
            logger.info(f"Session {session_id} is not older than 2 minutes, so it was not stopped.")
    else:
        logger.warning(f"Session {session_id} data is invalid, missing 'time' field.")

@csrf_exempt
@require_POST
def whatsapp_hook(request):
    # Check private IP using X-Forwarded-For or other headers
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        client_ip = x_forwarded_for.split(',')[0].strip()
    else:
        client_ip = request.META.get('REMOTE_ADDR')
    
    # Log the IP for debugging
    logger.debug(f"Client IP: {client_ip}")
    logger.debug(f"All META headers: {request.META}")
    
    if client_ip != '20.50.192.219':
        return HttpResponseForbidden(f"Forbidden: Invalid source IP {client_ip}")
        
    body_unicode = request.body.decode('utf-8')
    try:
        body_data = json.loads(body_unicode)
    except json.JSONDecodeError:
        return JsonResponse({"message": "Webhook processed successfully"}, status=200)

    if body_data.get('event') == 'session.status':
        session_status_process(body_data)
        return JsonResponse({"message": "Webhook processed successfully"}, status=200)
    if body_data.get('event') == 'message':
        message_process(body_data)
        return JsonResponse({"message": "Webhook processed successfully"}, status=200)
    return JsonResponse({"message": "Webhook processed successfully"}, status=200)


def session_status_process(body_unicode):
    session_status = body_unicode.get('payload', {}).get('status')
    me_data = body_unicode.get('me', {})
    store_id = body_unicode.get('metadata', '').get('user.id')
    number = me_data.get('id') if me_data else None
    
    store = get_store_by_id(store_id)
    userlink = get_user_store_link(store_id)
    user = userlink.user
    
    if session_status not in ['WORKING', 'FAILED', 'STOPPED', 'SCAN_QR_CODE']:
        logger.error(f"Unknown session status: {session_status}")
        return

    if session_status == 'SCAN_QR_CODE':
        logger.info(f"Session {user.session_id} is handled by function stop_or_store_session.")
        stop_or_store_session(user.session_id, user)
        return
        
    if not number:
        logger.error("Phone number is missing in session data.")
        return



    if not user:
        logger.error(f"No user found for store_id: {store_id}")
        return

    try:
        if session_status == 'WORKING':
            # clear user model cache
            if user.connected:
                logger.error("User is already connected.")
                return
            success, message = admin_messages.send_working_message(number, "working")
            if not success:
                logger.error(f"Failed to send working message: {message}")
            user.connected = True
            user.phone_number = number
        elif session_status in ['FAILED', 'STOPPED']:
            success, message = admin_messages.send_working_message(number, "disconnect")
            if not success:
                logger.error(f"Failed to send disconnect message: {message}")
            user.connected = False
            user.phone_number = number
        user.save()
    except Exception as e:
        logger.error(f"Error processing session status: {e}")



def message_process(body_unicode):
    # Ensure the message is not sent from yourself
    store_id = body_unicode.get('metadata', {}).get('user.id')  # Store ID
    store = get_store_by_id(store_id)
    userlink = get_user_store_link(store_id)
    user = userlink.user
    messages_limit = get_subscription(store_id).messages_limit

    if not user.connected:
        logger.info("User is not connected.")
        Notification.objects.create(store=store, message="الواتساب غير متصل. يرجى تحديث البيانات.")
        return

    if not store.subscription.staticbot:
        logger.info("StaticBot is disabled for this store subscription.")
        return

    if store.subscription_message_count >= messages_limit:
        logger.info(f"Message limit reached: {store.subscription_message_count} messages sent.")
        return


    if body_unicode.get('payload', {}).get('fromMe') == False:
        from_number = body_unicode.get('payload', {}).get('from')  # Customer number
        staticbotstart = get_staticbot_start(store)
        success = False



        if not store.botenabled:
            logger.info("Bot is disabled for this store.")
            return  # No StaticBotStart configured for this store
        
        # Calculate the cutoff time
        cutoff_time = now() - timedelta(hours=staticbotstart.hours)
        
        # Check if a log exists for the same customer, store, and within the cutoff time
        recent_log_exists = get_recent_log(from_number, store, cutoff_time)

        payload_message = body_unicode.get('payload', {}).get('body')
        if not recent_log_exists and staticbotstart and staticbotstart.enabled:


            success, message = send_whatsapp_message(from_number, staticbotstart.return_message, user.session_id, store)
            
            if success:
                StaticBotLog.objects.create(
                    customer=from_number,
                    store=store,
                    time=now()  # Record the time of the message
                )
                staticbotstartmessage, created = StaticBotStartMessage.objects.get_or_create(store=store, defaults={'count': 0})
                staticbotstartmessage.count += 1
                staticbotstartmessage.save()
            else:
                logger.error("No message sent using StaticBotStart.")

        elif recent_log_exists:
            # Use the other static bots only when there is a recent log
            logger.info(f"Using StaticBots for message processing.")
            staticbots = get_staticbots(store)
            for staticbot in staticbots:
                if payload_message is not None:
                    if staticbot.condition == 1:  # Exact text
                        if payload_message == staticbot.message:
                            success, message = send_whatsapp_message(from_number, staticbot.return_message, user.session_id, store)
                    elif staticbot.condition == 2:  # Contains text
                        if payload_message in staticbot.message:
                            success, message = send_whatsapp_message(from_number, staticbot.return_message, user.session_id, store)
                    elif staticbot.condition == 3:  # Any text
                        success, message = send_whatsapp_message(from_number, staticbot.return_message, user.session_id, store)

                    if success:
                        staticbotmessage, created = StaticBotMessage.objects.get_or_create(store=store, bot=staticbot, defaults={'count': 0})
                        staticbotmessage.count += 1
                        staticbotmessage.save()  # Don't forget to save the updated count
                        break

                if not success:
                    logger.error("No message sent for the incoming payload.")
