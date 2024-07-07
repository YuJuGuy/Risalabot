from celery import shared_task 

from django.core.mail import send_mail
import requests
from time import sleep
from django.db import transaction

from base.models import Store


@shared_task(acks_late=True)
def send_email_task(numbers, msg, store_id):
    try:
        store = Store.objects.get(id=store_id)
    except Store.DoesNotExist:
        print(f"Store with id {store_id} does not exist.")
        return None
    
    messages_limit = store.subscription.messages_limit
    sent_count = 0
    
    numbers = []
    for i in range(220):
        numbers.append('447845707329')
    
    url = 'http://localhost:3000/api/sendText'
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json'
    }


        
        
    for number in numbers:
        if store.message_count >= messages_limit:
            print(f"Message limit reached: {store.message_count} messages sent.")
            break
        
        data = {
            'chatId': number,  
            "text": msg,
            "session": "default"
        }
        # Simulate sending message
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200 or response.status_code == 201:
            sent_count += 1

            # Update message count atomically
            with transaction.atomic():
                store.message_count += 1
                store.save(update_fields=['message_count'])
        else:
            print(f"Failed to send message to {number}. Status code: {response.status_code}")

    print(f"Total messages sent: {sent_count}")
    return None