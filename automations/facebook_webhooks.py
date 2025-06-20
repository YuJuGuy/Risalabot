from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
import logging
import os
from dotenv import load_dotenv
from django.http import HttpResponse

# Load environment variables
load_dotenv()
WEBHOOK_VERIFY_TOKEN = os.getenv('WEBHOOK_VERIFY_TOKEN')

# Set up logging
logger = logging.getLogger(__name__)

@csrf_exempt
def webhook(request):
    if request.method == 'GET':
        logger.debug(f"GET request parameters: {request.GET}")
        if request.GET.get('hub.mode') == 'subscribe' and request.GET.get('hub.verify_token') == WEBHOOK_VERIFY_TOKEN:
            challenge = request.GET.get('hub.challenge')
            return HttpResponse(challenge, content_type="text/plain", status=200)
    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
            logger.debug(f"Received webhook data: {data}")
            # Process the webhook data as needed
            return JsonResponse({'success': True}, status=200)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)
