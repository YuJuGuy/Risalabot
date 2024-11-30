from celery import shared_task, chain
import requests
from django.db import transaction
from base.apis import create_coupon
from datetime import datetime, timedelta, timezone
from django.utils.crypto import get_random_string
from base.models import Store, Campaign, UserStoreLink, Flow, FlowStep, TextConfig, TimeDelayConfig, CouponConfig, AbandonedCart
import logging
import pytz
from celery import current_app
from redis.exceptions import LockError
from django.conf import settings
from redis import Redis

# Initialize Redis connection (centralize this if used elsewhere)
redis_instance = Redis(host='localhost', port=6379, db=0)

logging.basicConfig(level=logging.INFO)
ksa_timezone = pytz.timezone("Asia/Riyadh")




replacements = {
    '{اسم العميل}': 'customer_full_name',
    '{الاسم الاول}': 'customer_first_name',
    '{الايميل}': 'customer_email',
    '{رقم العميل}': 'customer_number',
    '{الدولة}': 'customer_country',
    '{رابط التتبع}': 'tracking_link',
    '{الحالة}': 'status_arabic',
    '{السعر}': 'total_amount',
    '{رابط التقييم}': 'rating_link',
    '{رابط السلة}': 'cart_link',
    '{الكوبون}': 'code',
}



def send_whatsapp_message(store, number, msg, session):
    """
    Send a WhatsApp message and update message count atomically.
    """

    # Lock the store row
    with transaction.atomic():
        store = Store.objects.select_for_update().get(id=store.id)
        messages_limit = store.subscription.messages_limit

        if store.subscription_message_count >= messages_limit:
            return False, f"Message limit reached: {store.subscription_message_count} messages sent."

        # Increment the message count
        store.subscription_message_count += 1
        store.save(update_fields=['subscription_message_count'])

    # Proceed with sending the message
    url = 'http://localhost:3000/api/sendText'
    headers = {'accept': 'application/json', 'Content-Type': 'application/json'}

    number = clean_number(number)
    data = {
        'chatId': number,
        "text": msg,
        "session": session
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        logging.info(response.json())
        if response.status_code in [200, 201]:
            return True, "Message sent successfully."
        else:
            return False, f"Failed to send message. Status code: {response.status_code}"
    except requests.exceptions.RequestException as e:
        return False, f"Error occurred when sending message: {e}"

    
    
@shared_task(bind=True, max_retries=3)
def send_whatsapp_message_task(self, data):
    # Use Celery's Redis connection

    lock_key = f"store_{data['store_id']}_lock"
    lock = redis_instance.lock(lock_key, timeout=60)  # Lock expires after 60 seconds

    try:
        if not lock.acquire(blocking=True):
            logging.info(f"Task is already processing messages for store {data['store_id']}")
            return None  # Exit if another task is already processing

        # Proceed with task logic
        store = Store.objects.get(store_id=data['store_id'])
        campaign = Campaign.objects.get(id=data['campaign_id'], store=store)

        if campaign.status != 'scheduled':
            logging.info(f"Campaign with id {data['campaign_id']} is not scheduled")
            return None

        session = UserStoreLink.objects.filter(store=store).first().user.session_id

        sent_count = 0
        failed_count = 0

        for customer in data['customers_data']:
            store.refresh_from_db()

            if store.subscription_message_count >= store.subscription.messages_limit:
                logging.info("Message limit reached. Stopping further processing.")
                break  # Stop sending messages if the limit is reached

            if '{' in data['msg']:
                replacements = {
                    '{اسم العميل}': customer.get('name', ''),
                    '{رقم العميل}': customer.get('phone', ''),
                    '{الايميل}': customer.get('email', ''),
                    '{الاسم الاول}': customer.get('first_name', ''),
                    '{الدولة}': customer.get('location', ''),
                }
                for placeholder, value in replacements.items():
                    data['msg'] = data['msg'].replace(placeholder, value)

            success, message = send_whatsapp_message(store, customer['phone'], data['msg'], session)
            if success:
                sent_count += 1
                with transaction.atomic():
                    campaign.messages_sent += 1
                    campaign.save(update_fields=['messages_sent'])
            else:
                failed_count += 1

        campaign.status = 'sent' if failed_count == 0 else 'failed'
        campaign.save(update_fields=['status'])

    except Store.DoesNotExist:
        logging.info(f"Store with id {data['store_id']} does not exist.")
    except Campaign.DoesNotExist:
        logging.info(f"Campaign with id {data['campaign_id']} does not exist")
    except LockError as e:
        logging.error(f"Failed to acquire lock: {e}")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
    finally:
        lock.release()







@shared_task(bind=True, max_retries=3)
def process_flows_task(self, flow_ids, flow_data, current_step_index=0):
    """
    Celery task to process flows asynchronously using the flow IDs.
    The current_step_index keeps track of the current step in the flow.
    """
    flows = Flow.objects.filter(id__in=flow_ids)
    
    try:
        store = Store.objects.get(store_id=flow_data['store_id'])
        user = UserStoreLink.objects.filter(store=store).first().user
    except Store.DoesNotExist:
        logging.info(f"Store with id {flow_data['store_id']} does not exist.")
        return None

    for flow in flows:
        # Order flow steps and process starting from the current step
        flow_steps = FlowStep.objects.filter(flow=flow).order_by('order').select_related('text_config', 'time_delay_config', 'coupon_config')
        session = UserStoreLink.objects.filter(store=store).first().user.session_id

        abandoned_cart_created = False  # Track if abandoned cart is created

        if flow_steps:
            # Process steps starting from the current step index
            for index, flow_step in enumerate(flow_steps[current_step_index:], start=current_step_index):
                
                # Send SMS
                if flow_step.action_type.name == 'sms':
                    text_config = TextConfig.objects.get(flow_step=flow_step)
                  
                  # Apply all replacements in one loop
                    if '{' in text_config.message:
                         for placeholder, key in replacements.items():
                            value = flow_data.get(key, '')
                            text_config.message = text_config.message.replace(placeholder, value)
                    
                
                    # Send the message
                    success, message = send_whatsapp_message(store, flow_data['customer_phone'], text_config.message, session)
                    # If the message is sent successfully, update the flow messages sent count
                    if success:
                        with transaction.atomic():
                            flow.messages_sent += 1
                            flow.save(update_fields=['messages_sent'])
                        logging.info(f"Message sent to {flow_data['customer_phone']}")
                        
                        # Create abandoned cart if the flow trigger is abandoned cart
                        if flow.trigger.event_type == 'abandoned_cart' and not abandoned_cart_created:
                            if '{رابط السلة}' in text_config.message:
                                AbandonedCart.objects.create(store=store, customer_id=flow_data['customer_id'], cart_id=flow_data['cart_id'], flow_id=flow.id)
                                abandoned_cart_created = True  # Mark as created

                    else:
                        logging.info(f"Failed to send message to {flow_data['customer_phone']}: {message}")
                        
                # Create coupon
                elif flow_step.action_type.name == 'coupon':
                    coupon_config = CouponConfig.objects.get(flow_step=flow_step)
                    # Generate a random coupon code
                    code = get_random_string(12).upper()
                    # Prepare the coupon data
                    coupondata = {
                        'code': code,
                        'type': coupon_config.type,
                        'amount': coupon_config.amount,
                        'maximum_amount': coupon_config.maximum_amount,
                        'start_date': datetime.now(ksa_timezone).strftime("%Y-%m-%d"),
                        'expiry_date': (datetime.now(ksa_timezone) + timedelta(days=coupon_config.expire_in)).strftime("%Y-%m-%d"),
                        'free_shipping': coupon_config.free_shipping,
                        'exclude_sale_products': coupon_config.exclude_sale_products,
                        'message': coupon_config.message
                    }
                        
                    # Apply all replacements in one loop
                    if '{' in coupon_config.message:
                        for placeholder, key in replacements.items():
                            value = flow_data.get(key, '')
                            coupon_config.message = coupon_config.message.replace(placeholder, value)
                           
                    result = create_coupon(user, coupondata)

                    if result['success']:
                        # Handle success, coupon creation was successful
                        logging.info("Coupon created successfully:", result['data'])
                        success, message = send_whatsapp_message(store, flow_data['customer_phone'],coupon_config.message, session)
                        if success:
                            with transaction.atomic():
                                flow.messages_sent += 1
                                flow.save(update_fields=['messages_sent'])
                            # Create abandoned cart if the flow trigger is abandoned cart
                            if flow.trigger.event_type == 'abandoned_cart' and not abandoned_cart_created:
                                if '{رابط السلة}' in coupon_config.message:
                                    AbandonedCart.objects.create(store=store, customer_id=flow_data['customer_id'], cart_id=flow_data['cart_id'], flow_id=flow.id)
                                    abandoned_cart_created = True  # Mark as created
                    else:
                        # Handle failure, coupon creation failed
                        logging.error("Failed to create coupon: %s", result['message'])
                                        

                elif flow_step.action_type.name == 'delay':
                    time_delay_config = TimeDelayConfig.objects.get(flow_step=flow_step)
                    delay_seconds = convert_delay_to_seconds(time_delay_config.delay_time, time_delay_config.delay_type)

                    if delay_seconds:
                        # Schedule the task to resume after the delay, passing the next step index
                        self.apply_async(
                            args=[flow_ids, flow_data, index + 1],  # Pass the next step index
                            countdown=delay_seconds
                        )
                        return  # Exit the task to wait for the delayed execution
                
            
        # Log when the flow is fully executed

        logging.info(f"Flow {flow.id} for store {store.store_id} has been fully executed.")
    
    return None






def convert_delay_to_seconds(delay_time, delay_type):
    """
    Convert delay time from hours or days into seconds for use with Celery countdown.
    """
    if delay_type == 'hours':
        return delay_time * 3600  # Convert hours to seconds
    elif delay_type == 'days':
        return delay_time * 86400  # Convert days to seconds
    elif delay_type == 'minutes':
        return delay_time * 60  # Convert minutes to seconds
    else:
        return None  # If invalid delay type
    
    

def clean_number(number):
    #remove the + and spaces from the number
    return number.replace('+', '').replace(' ', '')
    
    
    


