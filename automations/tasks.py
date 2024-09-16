from celery import shared_task 

from django.core.mail import send_mail
import requests
from time import sleep
from django.db import transaction


from base.models import Store, Campaign


@shared_task(acks_late=True)
def send_email_task(numbers, msg, store_id, campaign_id):
    try:
        store = Store.objects.get(id=store_id)
        campaign = Campaign.objects.get(id=campaign_id, store=store)
    except Store.DoesNotExist:
        print(f"Store with id {store_id} does not exist.")
        campaign.status = 'failed'
        campaign.save(update_fields=['status'])
        return None
    except Campaign.DoesNotExist:
        print(f"Campaign with id {campaign_id} does not exist.")
        return None
    
    messages_limit = store.subscription.messages_limit
    sent_count = 0

    # Simulate the list of numbers

    url = 'http://localhost:3000/api/sendText'
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json'
    }

    try:
        for number in numbers:
            if store.message_count >= messages_limit:
                print(f"Message limit reached: {store.message_count} messages sent.")
                break

            data = {
                'chatId': number,
                "text": msg,
                "session": "default"
            }

            response = requests.post(url, headers=headers, json=data)
            if response.status_code == 200 or response.status_code == 201:
                sent_count += 1

                # Update message count atomically
                with transaction.atomic():
                    store.message_count += 1
                    store.save(update_fields=['message_count'])
            else:
                print(f"Failed to send message to {number}. Status code: {response.status_code}")

        # Mark the campaign as successful if all messages are sent
        campaign.status = 'completed'
        campaign.save(update_fields=['status'])

    except requests.exceptions.ConnectionError as e:
        print(f"Connection error occurred: {e}")
        campaign.status = 'failed'
        campaign.save(update_fields=['status'])

    print(f"Total messages sent: {sent_count}")
    return None
