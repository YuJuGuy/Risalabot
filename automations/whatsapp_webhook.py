from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from . import admin_messages
import json
from base.models import User, Store, UserStoreLink
import logging

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def whatsapp_hook(request):
    body_unicode = request.body.decode('utf-8')
    try:
        body_data = json.loads(body_unicode)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    if body_data.get('event') == 'session.status':
        session_status_process(body_data)
        return JsonResponse({"message": "Webhook processed successfully"}, status=200)
    if body_data.get('event') == 'message':
        return JsonResponse({"message": "Webhook processed successfully"}, status=200)
    return JsonResponse({"message": "Webhook processed successfully"}, status=200)


def session_status_process(payload_json):
    session_status = payload_json.get('payload', {}).get('status')
    me_data = payload_json.get('me', {})
    store_id = payload_json.get('metadata', '').get('user.id')
    number = me_data.get('id') if me_data else None

    if session_status not in ['WORKING', 'FAILED', 'STOPPED']:
        logger.error(f"Unknown session status: {session_status}")
        return
        
    if not number:
        logger.error("Phone number is missing in session data.")
        return

    user = UserStoreLink.objects.filter(store__store_id=store_id).first()
    if not user:
        logger.error(f"No user found for store_id: {store_id}")
        return

    try:
        if session_status == 'WORKING':
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
