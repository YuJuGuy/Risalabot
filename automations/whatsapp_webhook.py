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
        if datetime.now() - session_time > timedelta(seconds=120):
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
    
    store = Store.objects.filter(store_id=store_id).first()
    user_store_link = UserStoreLink.objects.get(store__store_id=store_id)
    user = user_store_link.user
    
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
    store = Store.objects.filter(store_id=store_id).first()
    user_store_link = UserStoreLink.objects.get(store__store_id=store_id)
    user = user_store_link.user
    messages_limit = store.subscription.messages_limit

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
        staticbotstart = StaticBotStart.objects.filter(store=store).first()
        success = False



        if not store.botenabled:
            logger.info("Bot is disabled for this store.")
            return  # No StaticBotStart configured for this store
        
        # Calculate the cutoff time
        cutoff_time = now() - timedelta(hours=staticbotstart.hours)
        
        # Check if a log exists for the same customer, store, and within the cutoff time
        recent_log_exists = StaticBotLog.objects.filter(
            customer=from_number,
            store=store,
            time__gte=cutoff_time  # Within the last `hours`
        ).exists()

        payload_message = body_unicode.get('payload', {}).get('body')
        if not recent_log_exists and staticbotstart and staticbotstart.enabled:


            success = send_whatsapp_message(from_number, staticbotstart.return_message, user.session_id)
            
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
            staticbots = StaticBot.objects.filter(store=store)
            for staticbot in staticbots:
                if payload_message is not None:
                    if staticbot.condition == 1:  # Exact text
                        if payload_message == staticbot.message:
                            success = send_whatsapp_message(from_number, staticbot.return_message, user.session_id)
                    elif staticbot.condition == 2:  # Contains text
                        if payload_message in staticbot.message:
                            success = send_whatsapp_message(from_number, staticbot.return_message, user.session_id)
                    elif staticbot.condition == 3:  # Any text
                        success = send_whatsapp_message(from_number, staticbot.return_message, user.session_id)

                    if success:
                        staticbotmessage, created = StaticBotMessage.objects.get_or_create(store=store, bot=staticbot, defaults={'count': 0})
                        staticbotmessage.count += 1
                        staticbotmessage.save()  # Don't forget to save the updated count
                        break

                if not success:
                    logger.error("No message sent for the incoming payload.")
