from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import hashlib
import hmac
import os
from base.models import Trigger
from dotenv import load_dotenv  
import logging
import json
from base.models import User, Store, Flow,UserStoreLink

# log to a file

logger = logging.getLogger(__name__)

class FlowBuilderError(Exception):
    """Custom exception for Flow Builder specific errors"""
    pass


load_dotenv()
# Replace with your actual Signature token
SIGNATURE_TOKEN = os.getenv('SIGNATURE_TOKEN')

@csrf_exempt  # Disable CSRF protection for webhook endpoint
@require_POST  # Only allow POST requests
def webhook(request):
    # Get headers
    security_strategy = request.headers.get('X-Salla-Security-Strategy')
    signature = request.headers.get('X-Salla-Signature')
    # Get payload (assuming it's JSON)
    payload = request.body
    

    if security_strategy == "Signature" and signature:
        # Calculate expected HMAC signature
        expected_signature = hmac.new(
            SIGNATURE_TOKEN.encode('utf-8'),
            msg=payload,
            digestmod=hashlib.sha256
        ).hexdigest()

        # Compare the calculated signature with the received signature
        if hmac.compare_digest(expected_signature, signature):
            try:
                payload_json = json.loads(payload.decode('utf-8'))
                event = payload_json.get('event')
                logging.info(f"Signature verified successfully. Event: {event}")
                
                # Check if the event matches any trigger using a single database query
                matching_trigger = Trigger.objects.filter(event_type=event).exists()
                
                if matching_trigger:
                    process_webhook(payload_json)
                else:
                    logging.warning(f"Unrecognized event type: {event}")
                return JsonResponse({"message": "Webhook processed successfully"}, status=200)
            except json.JSONDecodeError:
                logging.error("Failed to decode JSON payload")
                return JsonResponse({"message": "Invalid JSON payload"}, status=400)
        else:
            # Signature is not valid
            logging.error("Signature verification failed")
            return JsonResponse({"message": "Signature verification failed"}, status=403)
    else:
        # Invalid security strategy or missing signature
        logging.error("Invalid security strategy or missing signature header")
        return JsonResponse({"message": "Invalid security strategy or missing signature header"}, status=403)
    
    
    
def process_webhook(payload):
    event = payload.get('event')
    store_id = payload.get('merchant')
    
    # Find the matching trigger
    matching_trigger = Trigger.objects.filter(event_type=event).first()
    
    if matching_trigger:
        # Find the UserStoreLink for the given store_id
        user_store_link = UserStoreLink.objects.filter(store__store_id=store_id).first()
        
        if user_store_link:
            # Find the all the flows associated with the user and the matching trigger
            flows = Flow.objects.filter(
                owner=user_store_link.user,
                trigger=matching_trigger
            ).all()
            
            if flows:
                print(f"Found flow: {flows}")
                # Process the flow here
            else:
                print(f"No flow found for user {user_store_link.user} and trigger {matching_trigger}")
        else:
            print(f"No UserStoreLink found for store_id: {store_id}")
    else:
        print(f"No matching trigger found for event: {event}")

    

