from celery import shared_task, chain
import requests
from django.db import transaction
from base.apis import create_coupon
from datetime import datetime, timedelta, timezone
from django.utils.crypto import get_random_string
from base.models import Store, Campaign, UserStoreLink, Flow, FlowStep, TextConfig, TimeDelayConfig, CouponConfig, AbandonedCart, Notification
import logging
import pytz
from automations.whatsapp_api import send_whatsapp_message

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
        # Access the first dictionary in the data list
        if isinstance(data, list):
            data = data[0]

        store = Store.objects.get(store_id=data['store_id'])

        userstorelink = UserStoreLink.objects.get(store=store)
        user = userstorelink.user
        

        if not user.connected:
            logging.info("User is not connected.")
            Notification.objects.create(store=store, message="الواتساب غير متصل. يرجى تحديث البيانات.")
            return None
            return
        
        # Check if the campaign exists and has the correct status
        campaign = Campaign.objects.get(id=data['campaign_id'], store=store)
        if campaign.status != 'scheduled':
            logging.info(f"Campaign with id {data['campaign_id']} is not scheduled")
            return None

        session = UserStoreLink.objects.filter(store=store).first().user.session_id
    except Store.DoesNotExist:
        logging.info(f"Store with id {data['store_id']} does not exist.")
        return None
    except Campaign.DoesNotExist:
        logging.info(f"Campaign with id {data['campaign_id']} does not exist")
        return None
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return None

    sent_count = 0
    failed_count = 0  # Track failed messages

    # Sending messages in batch or all at once
    for customer in data['customers_data']:
        # Only process replacements if the message contains placeholders
        if '{' in data['msg']:
            replacements = {
                '{اسم العميل}': customer.get('name', ''),
                '{رقم العميل}': customer.get('phone', ''),
                '{الايميل}': customer.get('email', ''),
                '{الاسم الاول}': customer.get('first_name', ''),
                '{الدولة}': customer.get('location', ''),
                # Add other placeholders here as needed
            }
            # Apply all replacements in one loop
            for placeholder, value in replacements.items():
                data['msg'] = data['msg'].replace(placeholder, value)

        # Send the WhatsApp message
        messages_limit = store.subscription.messages_limit
        if store.subscription_message_count >= messages_limit:
            return False, f"Message limit reached: {store.subscription_message_count} messages sent."
        success, message = send_whatsapp_message(customer['phone'], data['msg'], session)
        if success:
            sent_count += 1
            with transaction.atomic():
                campaign.messages_sent += 1
                campaign.save(update_fields=['messages_sent'])
        else:
            failed_count += 1

    # Update campaign status
    campaign.status = 'sent' if failed_count == 0 else 'failed'
    campaign.save(update_fields=['status'])

    # Schedule next batch if there's more messages and a schedule_next_in is provided
    if data.get('schedule_next_in'):
        self.apply_async(
            args=[data],
            countdown=data['schedule_next_in']
        )

    return None







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

    if not user.connected:
        logging.info("User is not connected.")

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
                        messages_limit = store.subscription.messages_limit
                        if store.subscription_message_count >= messages_limit:
                            return False, f"Message limit reached: {store.subscription_message_count} messages sent."
                        success, message = send_whatsapp_message(flow_data['customer_phone'],coupon_config.message, session)
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
    
    


    
    


