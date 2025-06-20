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
from datetime import datetime, timezone
from django.core.mail import send_mail
from django.utils.crypto import get_random_string
from django.contrib.auth.hashers import make_password

# Load environment variables from .env file
load_dotenv()

# Log to a file
logger = logging.getLogger(__name__)

@csrf_exempt
@require_POST
def webhook(request):

    # Print all environment variables for debugging

    # Assuming the token is sent in a header called 'x-salla-signature'
    received_signature = request.headers.get('x-salla-signature')
    secret = os.getenv('WEBHOOK_SIGNATURE')  # Ensure this is set in your environment

    # Compute HMAC using the request body and secret
    computedHMAC = hmac.new(
        key=secret.encode('utf-8'),
        msg=request.body,
        digestmod=hashlib.sha256
    ).hexdigest()

    # Compare the computed HMAC with the received signature
    if received_signature != computedHMAC:
        logger.info("Signature verified successfully")

        try:
            payload_json = json.loads(request.body.decode('utf-8'))
            event = payload_json.get('event')
            logger.info(f"Token verified successfully. Event: {event}")
            
            # Process the event as before
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
                process_flow_webhook(payload_json)
                return JsonResponse({"message": "Webhook processed successfully"}, status=200)
            
            return JsonResponse({"message": "Webhook processed successfully"}, status=200)

        except json.JSONDecodeError:
            logger.error("Failed to decode JSON payload")
            return JsonResponse({"message": "Invalid JSON payload"}, status=400)
    else:
        logger.error("Signature verification failed")
        return JsonResponse({"message": "Unauthorized"}, status=401)


def process_flow_webhook(payload):
    try:
        event = payload.get('event')
        store_id = str(payload.get('merchant', ''))
        logger.info(payload)

        if event == 'order.updated' or event == 'order.status.updated':
            # remove the word .status
            if event == 'order.status.updated':
                status_id = payload.get('data', {}).get('order', {}).get('status', {}).get('id', '')
            else:
                status_id = payload.get('data', {}).get('status', {}).get('id', '')
                    
            event = event.replace('.status', '')
            # Correctly access the status ID from the order object
            event = f"{event}.{status_id}"
            logger.info(f"Event after status update: {event}")
        
            
            
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
            logger.info(Trigger.objects.all())
            raise ValueError(f"No matching trigger found for event: {event}")
            
        logger.info(f"Matching trigger found: {matching_trigger}")
        
        logger.info(f"")
        
        
        # Prepare flow data with safe dictionary access
        status = data.get('status', {})
        if isinstance(status, dict):
            status_arabic = str(status.get('name', ''))
        else:
            status_arabic = str(status)  # If status is a string, use it directly
        flow_data = {
            'store_id': str(store_id),
            'customer_full_name': f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip(),
            'customer_first_name': str(customer.get('first_name', '')),
            'customer_country': str(customer.get('country', '')),
            'customer_email': str(customer.get('email', '')),
            'customer_phone': f"{customer.get('mobile_code', '')}{customer.get('mobile', '')}",
            'tracking_link': str((data.get('shipping', {}) or {}).get('shipment', {}).get('tracking_link', '')),
            'status_arabic': status_arabic,
            'rating_link': str((data.get('urls', {}) or {}).get('rating_link', '')),
            'total_amount': str((data.get('amounts', {}) or {}).get('total', {}).get('amount', '')),
            'cart_link': str(data.get('checkout_url', '')),
            'customer_id': str(customer.get('id', '')),
            'cart_id': str(data.get('id', '')) if event == 'abandoned.cart' else '',
        }
        
        logger.info(f"Flow data captured")
        

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
    event = str(payload.get('event', ''))
    logging.info(f"App webhook payload: {payload}")
    try:                
        if event == 'app.store.authorize':
            # Get store info from the payload
            store_info = payload.get('data', {}).get('store', {})
            store_email = store_info.get('email', 'yousef@risalabot.com')
            
            # Create or update store
            date = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
            store, created = Store.objects.update_or_create(
                store_id=store_id,
                defaults={
                    'store_name': store_info.get('name', ''),
                    'store_domain': store_info.get('domain', ''),
                    'subscription_date': date,
                    'token_refresh_date': date,
                    'access_token': payload.get('data', {}).get('access_token', ''),
                    'refresh_token': payload.get('data', {}).get('refresh_token', ''),
                    'token_valid': True,
                    'subscribtion': 'أساسي'
                }
            )

            # Create user if store has email and no existing link
            user_created = False  # Initialize the variable
            if store_email and not UserStoreLink.objects.filter(store=store).exists():
                # Generate random password
                random_password = get_random_string(length=12)
                
                # Create or get user
                user, user_created = User.objects.get_or_create(
                    email=store_email,
                    defaults={
                        'username': store_email,
                        'password': make_password(random_password),
                        'session_id': get_random_string(length=32)
                    }
                )

                # Create user-store link or update if it exists
                UserStoreLink.objects.update_or_create(user=user, store=store)

                # Send email with credentials if new user
                if user_created:
                    send_mail(
                        'Your Risalabot Account Credentials',
                        f'Your account has been created.\nEmail: {store_email}\nPassword: {random_password}\n\nPlease change your password after logging in.',
                        'noreply@risalabot.com',
                        [store_email],
                        fail_silently=False,
                    )

            Notification.objects.create(
                store=store, 
                message=f"تم تفعيل التطبيق للمتجر {store.store_id}"
            )
            logging.info(f"Store {'created' if created else 'updated'}: {store_id}")
            if store_email:
                logging.info(f"User status - Email: {store_email}, Created: {user_created}")
            return JsonResponse({"message": "Webhook processed successfully"}, status=200)
        
        elif event == 'app.subscription.started' or event == 'app.subscription.renewed':
            store = Store.objects.get(store_id=store_id)
            MonthlyPayments.objects.create(store=store, reference_number=payload.get('data', {}).get('id', ''), subscribtion=payload.get('data', {}).get('plan_name', ''), amount=payload.get('data', {}).get('price', ''))
            Store.objects.filter(store_id=store_id).update(subscription_date=datetime.now(timezone.utc), subscribtion=payload.get('data', {}).get('plan_name', ''))
            logging.info(f"App subscription started for store {store.store_id}")
            Notification.objects.create(store=store, message=f"تم تفعيل الاشتراك للمتجر {store.store_id}")
            return JsonResponse({"message": "Webhook processed successfully"}, status=200)
        
        elif event == 'app.trial.started':
            store = Store.objects.get(store_id=store_id)
            AppTrial.objects.create(store=store, reference_number=payload.get('data', {}).get('id', ''))
            logging.info(f"App trial started for store {store.store_id}")
            Notification.objects.create(store=store, message=f"تم تفعيل التجربة للمتجر {store.store_id}")
            return JsonResponse({"message": "Webhook processed successfully"}, status=200)
        
        elif event == 'app.installed':
            store = Store.objects.get(store_id=store_id)
            MonthlyInstallations.objects.create(store=store, reference_number=payload.get('data', {}).get('id', ''))
            logging.info(f"App installed for store {store.store_id}")
            Notification.objects.create(store=store, message=f"تم تثبيت التطبيق للمتجر {store.store_id}")
            return JsonResponse({"message": "Webhook processed successfully"}, status=200)
        
        elif event == 'app.subscription.expired' or event == 'app.subscription.canceled':
            store = Store.objects.get(store_id=store_id)
            Store.objects.filter(store_id=store_id).update(subscription_date=datetime.now(timezone.utc), subscription='')
            logging.info(f"App subscription expired for store {store.store_id}")
            Notification.objects.create(store=store, message=f"انتهت صلاحية الاشتراك للمتجر {store.store_id}")
            return JsonResponse({"message": "Webhook processed successfully"}, status=200)
        
        elif event == 'app.uninstalled':
            try:
                # Get store and associated user info before deletion
                store = Store.objects.get(store_id=store_id)
                user_store_link = UserStoreLink.objects.filter(store=store).first()
                
                if user_store_link:
                    user = user_store_link.user
                    user_email = user.email
                    
                    # Delete user (this will cascade delete UserStoreLink)
                    user.delete()
                    logging.info(f"User deleted for store {store_id}")
                    
                    # Send notification email
                    send_mail(
                        'Risalabot App Uninstalled',
                        'Your Risalabot app has been uninstalled. All your data has been removed from our system. If you wish to use our services again, please reinstall the app.',
                        'noreply@risalabot.com',
                        [user_email],
                        fail_silently=False,
                    )
                    
                # Delete store
                store.delete()
                logging.info(f"Store deleted: {store_id}")
                
                return JsonResponse({"message": "App uninstalled and data cleaned up successfully"}, status=200)
                
            except Store.DoesNotExist:
                logging.error(f"Store {store_id} not found during uninstall")
                return JsonResponse({"message": "Store not found"}, status=404)
            except Exception as e:
                logging.error(f"Error during app uninstall: {str(e)}")
                return JsonResponse({"message": "Error during uninstall"}, status=500)

    except Exception as e:
        logging.error(f"Error processing app webhook: {str(e)}")
        return JsonResponse({"message": "Error processing webhook"}, status=500)
            

