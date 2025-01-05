from celery import shared_task, chain, signature, group
import requests
from celery.exceptions import MaxRetriesExceededError
from django.db import transaction
from base.apis import create_coupon
from datetime import datetime, timedelta, timezone
from django.utils.crypto import get_random_string
from base.models import Store, Campaign, UserStoreLink, Flow, FlowStep, TextConfig, TimeDelayConfig, CouponConfig, AbandonedCart, Notification
import logging
import pytz
from automations.whatsapp_api import send_whatsapp_message
from base.Utils.cache_utils import get_store_by_id, get_user_store_link, get_subscription, get_user_by_store_id, get_session, get_campaign_by_id
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




    
    
@shared_task(bind=True, max_retries=3)
def send_whatsapp_message_task(self, data):
    try:
        if isinstance(data, list):
            data = data[0]

        store = get_store_by_id(data['store_id'])
        if not store:
            logging.info(f"المتجر بالمعرف {data['store_id']} غير موجود.")
            return None

        userstorelink = get_user_store_link(data['store_id'])
        if not userstorelink:
            logging.info("UserStoreLink not found")
            return None

        user = userstorelink.user
        if not user.connected:
            logging.info("المستخدم غير متصل.")
            Notification.objects.create(store=store, message="الواتساب غير متصل. يرجى تحديث البيانات.")
            return None

        campaign = get_campaign_by_id(data['campaign_id'])
        if campaign.status != 'scheduled':
            logging.info(f"الحملة بالمعرف {data['campaign_id']} ليست مجدولة")
            return None

        session = user.session_id

    except Campaign.DoesNotExist:
        logging.info(f"الحملة بالمعرف {data['campaign_id']} غير موجودة")
        return None
    except Exception as e:
        logging.error(f"خطأ غير متوقع: {e}")
        return None

    subscription = get_subscription(data['store_id'])
    if not subscription:
        logging.error("Subscription not found")
        return None

    delay = data.get('delay_in_seconds', 0)
    for i, customer in enumerate(data['customers_data']):
        if store.subscription_message_count >= subscription.messages_limit:
            logging.info(f"تم الوصول إلى الحد الأقصى للرسائل: {store.subscription_message_count} رسائل مرسلة.")
            break

        task_data = {
            "customer": customer,
            "msg": data['msg'],
            "campaign_id": data['campaign_id'],
            "store_id": data['store_id'],
            "session": session
        }
        send_single_message_task.apply_async(
            args=[task_data],
            countdown=i * delay
        )

    return "Messages scheduled successfully."

@shared_task
def send_single_message_task(task_data):
    try:
        customer = task_data['customer']
        campaign = get_campaign_by_id(task_data['campaign_id'])
        store = get_store_by_id(task_data['store_id'])
        subscription = get_subscription(task_data['store_id'])

        if not store or not subscription:
            return False, "Store or subscription not found"

        if store.subscription_message_count >= subscription.messages_limit:
            logging.info(f"تم الوصول إلى الحد الأقصى للرسائل: {store.subscription_message_count} رسائل مرسلة.")
            return False, "Reached maximum message limit."

        msg = task_data['msg']
        if '{' in msg:
            replacements = {
                '{اسم العميل}': customer.get('name', ''),
                '{رقم العميل}': customer.get('phone', ''),
                '{الايميل}': customer.get('email', ''),
                '{الاسم الاول}': customer.get('first_name', ''),
                '{الدولة}': customer.get('location', ''),
            }
            for placeholder, value in replacements.items():
                msg = msg.replace(placeholder, value)

        success, message = send_whatsapp_message(customer['phone'], msg, task_data['session'], store)
        if success:
            with transaction.atomic():
                campaign.messages_sent += 1
                campaign.save(update_fields=['messages_sent'])
            return True, "Message sent successfully."
        else:
            logging.info(f"Failed to send message to {customer['phone']}")
            return False, "Message failed."

    except Exception as e:
        logging.error(f"Error in send_single_message_task: {e}")
        return False, f"Error occurred: {e}"






@shared_task(bind=True, max_retries=3)
def process_flows_task(self, flow_ids, flow_data, current_step_index=0):
    """
    Celery task to process flows asynchronously using the flow IDs.
    The current_step_index keeps track of the current step in the flow.
    """
    flows = Flow.objects.filter(id__in=flow_ids)
    
    try:
        store = get_store_by_id(flow_data['store_id'])
        userlink = get_user_store_link(flow_data['store_id'])
        user = userlink.user
    except Store.DoesNotExist:
        logging.info(f"Store with id {flow_data['store_id']} does not exist.")
        return None

    if not user.connected:
        logging.info("User is not connected.")
        return None

    for flow in flows:
        # Order flow steps and process starting from the current step
        flow_steps = FlowStep.objects.filter(flow=flow).order_by('order').select_related('text_config', 'time_delay_config', 'coupon_config')
        session = get_session(user)

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
                    success, message = send_whatsapp_message(flow_data['customer_phone'], text_config.message, session, store)
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
                        messages_limit = store.subscription.messages_limit
                        if store.subscription_message_count >= messages_limit:
                            return False, f"Message limit reached: {store.subscription_message_count} messages sent."
                        success, message = send_whatsapp_message(flow_data['customer_phone'],coupon_config.message, session, store)
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
    
    


    
    


