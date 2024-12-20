from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import hashlib
import hmac
import os
from dotenv import load_dotenv  
import logging
import json
from base.models import User, Store, Flow,UserStoreLink, AbandonedCart, Subscription,Trigger, Notification
from automations.models import MonthlyInstallations, MonthlyPayments, AppTrial
from .tasks import process_flows_task

# log to a file

logger = logging.getLogger(__name__)


load_dotenv()
# Replace with your actual Signature token
SIGNATURE_TOKEN = os.getenv('SIGNATURE_TOKEN')

def verify_signature(payload, signature):
    expected_signature = hmac.new(
        SIGNATURE_TOKEN.encode('utf-8'),
        msg=payload,
        digestmod=hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected_signature, signature)



@csrf_exempt
@require_POST
def webhook(request):
    security_strategy = request.headers.get('X-Salla-Security-Strategy')
    signature = request.headers.get('X-Salla-Signature')
    payload = request.body

    if security_strategy == "Signature" and signature:
        if verify_signature(payload, signature):
            try:
                payload_json = json.loads(payload.decode('utf-8'))
                event = payload_json.get('event')
                logging.info(f"Signature verified successfully. Event: {event}")
                
                
                if "app" in event:
                    logging.info(f"App event processing")
                    process_app_webhook(payload_json)
                    return JsonResponse({"message": "Webhook processed successfully"}, status=200)

                if "review.added" in event:
                    if payload_json.get('data', {}).get('rating', '') == 5 or payload_json.get('data', {}).get('rating', '') == '5':
                        logging.info(f"Review event processing")
                        process_flow_webhook(payload_json)
                        return JsonResponse({"message": "Webhook processed successfully"}, status=200)

                if any(keyword in event for keyword in ["order", "abandoned", "customer.login"]):
                    logging.info(f"Order event processing")
                    print(payload_json)
                    process_flow_webhook(payload_json)
                    return JsonResponse({"message": "Webhook processed successfully"}, status=200)
                
                # Return a success response after processing
                return JsonResponse({"message": "Webhook processed successfully"}, status=200)

            except json.JSONDecodeError:
                logging.error("Failed to decode JSON payload")
                return JsonResponse({"message": "Invalid JSON payload"}, status=400)
        else:
            logging.error("Signature verification failed")
            return JsonResponse({"message": "Signature verification failed"}, status=403)
    else:
        logging.error("Invalid security strategy or missing signature header")
        return JsonResponse({"message": "Invalid security strategy or missing signature header"}, status=403)


def process_flow_webhook(payload):
    try:
        event = payload.get('event')
        store_id = str(payload.get('merchant', ''))

        if event == 'order.updated':
            status_id = payload.get('data', {}).get('status', {}).get('id', '')
            event = f"{event}.{status_id}"
        
            
            
        data = payload.get('data', {}) or {}
        customer = data.get('customer', {}) or {}
        
        if event == 'order.created':
            cart_reference_id = str(data.get('cart_reference_id', ''))
            if cart_reference_id:
                try:
                    # Check if the cart exists
                    if AbandonedCart.objects.filter(cart_id=cart_reference_id).exists():
                        # Update the cart to mark it as bought
                        AbandonedCart.objects.filter(cart_id=cart_reference_id).update(bought=True)
                    else:
                        logging.warning(f"Cart with ID {cart_reference_id} does not exist.")
                except Exception as e:
                    logging.error(f"Error processing webhook: {str(e)}")
                    
        # check if trigger for the user exists
        matching_trigger = Trigger.objects.filter(event_type=event).first()
        if not matching_trigger:
            raise ValueError(f"No matching trigger found for event: {event}")
        
        
        # Prepare flow data with safe dictionary access
        flow_data = {
            'store_id': str(store_id),
            'customer_full_name': f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip(),
            'customer_first_name': str(customer.get('first_name', '')),
            'customer_country': str(customer.get('country', '')),
            'customer_email': str(customer.get('email', '')),
            'customer_phone': f"{customer.get('mobile_code', '')}{customer.get('mobile', '')}",
            'tracking_link': str((data.get('shipping', {}) or {}).get('shipment', {}).get('tracking_link', '')),
            'status_arabic': str((data.get('status', {}) or {}).get('name', '')),
            'rating_link': str((data.get('urls', {}) or {}).get('rating_link', '')),
            'total_amount': str((data.get('amounts', {}) or {}).get('total', {}).get('amount', '')),
            'cart_link': str(data.get('checkout_url', '')),
            'customer_id': str(customer.get('id', '')),
            'cart_id': str(data.get('id', '')) if event == 'abandoned.cart' else '',
        }
        

        # Find matching trigger


        # Find UserStoreLink
        user_store_link = UserStoreLink.objects.filter(store__store_id=store_id).first()
        if not user_store_link:
            raise ValueError(f"No UserStoreLink found for store_id: {store_id}")

        # Find all matching flows for the trigger and user
        flows = Flow.objects.filter(
            owner=user_store_link.user,
            trigger=matching_trigger,
            status='active'
        ).select_related('trigger').all()

        if flows:
            logging.info(f"Found flow(s) for user {user_store_link.user}: {flows}")

            # Serialize flow IDs for Celery task
            flow_ids = list(flows.values_list('id', flat=True))

            # Pass the flow IDs and flow data to the Celery task
            process_flows_task.delay(flow_ids, flow_data)

        else:
            logging.warning(f"No flow found for user {user_store_link.user} and trigger {matching_trigger.event_type}")

    except Exception as e:
        logging.error(f"Error processing webhook: {str(e)}")

    
        
        
def process_app_webhook(payload):
    store_id = str(payload.get('merchant', ''))
    store = Store.objects.filter(store_id=store_id).first()
    event = str(payload.get('event', ''))
    try:                
        if store:
            if event == 'app.subscription.started' or event == 'app.subscription.renewed':
                MonthlyPayments.objects.create(store=store, reference_number=payload.get('data', {}).get('id', ''), subscribtion=payload.get('data', {}).get('plan_name', ''), amount=payload.get('data', {}).get('price', ''))
                Store.objects.filter(store_id=store_id).update(subscription_date=datetime.now(timezone.utc), subscribtion=payload.get('data', {}).get('plan_name', ''))
                logging.info(f"App subscription started for store {store.store_id}")
                Notification.objects.create(store=store, message=f"تم تفعيل الاشتراك للمتجر {store.store_id}")

            if event == 'app.trial.started':
                AppTrial.objects.create(store=store, reference_number=payload.get('data', {}).get('id', ''))
                logging.info(f"App trial started for store {store.store_id}")
                Notification.objects.create(store=store, message=f"تم تفعيل التجربة للمتجر {store.store_id}")

            if event == 'app.installed':
                MonthlyInstallations.objects.create(store=store, reference_number=payload.get('data', {}).get('id', ''))
                logging.info(f"App installed for store {store.store_id}")
                Notification.objects.create(store=store, message=f"تم تثبيت التطبيق للمتجر {store.store_id}")

            if event == 'app.subscription.expired' or event == 'app.subscription.canceled':
                Store.objects.filter(store_id=store_id).update(subscription_date=datetime.now(timezone.utc), subscription='')
                logging.info(f"App subscription expired for store {store.store_id}")
                Notification.objects.create(store=store, message=f"انتهت صلاحية الاشتراك للمتجر {store.store_id}")


    except Exception as e:
        logging.error(f"Error processing app webhook: {str(e)}")
            

