from celery import shared_task 

from django.core.mail import send_mail
import requests
from time import sleep
from django.db import transaction


from base.models import Store, Campaign, UserStoreLink, User, Flow, FlowStep, TextConfig, TimeDelayConfig
import logging

logging.basicConfig(level=logging.INFO)


def clean_number(number):
    #remove the + and spaces from the number
    return number.replace('+', '').replace(' ', '')

def send_whatsapp_message(store, number, msg, session):
    """
    Send a WhatsApp message to the given number and return whether it was successful.

    :param store: Store object (for message limit tracking)
    :param number: The phone number of the customer
    :param msg: The message text to send
    :param session: The session identifier for the WhatsApp API
    :return: (bool, str) - success flag, status message
    """
    messages_limit = store.subscription.messages_limit

    if store.subscription_message_count >= messages_limit:
        return False, f"Message limit reached: {store.subscription_message_count} messages sent."

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
    try:
        store = Store.objects.get(id=data['store_id'])
        campaign = Campaign.objects.get(id=data['campaign_id'], store=store)
        session = UserStoreLink.objects.filter(store=store).first().user.session_id
    except Store.DoesNotExist:
        logging.info(f"Store with id {data['store_id']} does not exist.")
        return None
    except Campaign.DoesNotExist:
        logging.info(f"Campaign with id {data['campaign_id']} does not exist.")
        return None

    sent_count = 0
    failed_count = 0  # Track failed messages

    # Sending messages in batch or all at once
    for number in data['customers_numbers']:
        success, message = send_whatsapp_message(store, number, data['msg'], session)
        if success:
            sent_count += 1
            with transaction.atomic():
                campaign.messages_sent += 1
                campaign.save(update_fields=['messages_sent'])
        else:
            failed_count += 1

    # Update campaign status
    campaign.status = 'completed' if failed_count == 0 else 'failed'
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
    except Store.DoesNotExist:
        logging.info(f"Store with id {flow_data['store_id']} does not exist.")
        return None

    for flow in flows:
        # Order flow steps and process starting from the current step
        flow_steps = FlowStep.objects.filter(flow=flow).order_by('order').select_related('text_config', 'time_delay_config')
        session = UserStoreLink.objects.filter(store=store).first().user.session_id

        if flow_steps:
            # Process steps starting from the current step index
            for index, flow_step in enumerate(flow_steps[current_step_index:], start=current_step_index):
                if flow_step.action_type.name == 'sms':
                    text_config = TextConfig.objects.get(flow_step=flow_step)
                    success, message = send_whatsapp_message(store, flow_data['customer_phone'], text_config.message, session)
                    if success:
                        with transaction.atomic():
                            flow.messages_sent += 1
                            flow.save(update_fields=['messages_sent'])
                        logging.info(f"Message sent to {flow_data['customer_phone']}")
                    else:
                        logging.info(f"Failed to send message to {flow_data['customer_phone']}: {message}")
                
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
