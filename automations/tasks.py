from celery import shared_task 

from django.core.mail import send_mail

from time import sleep
from django.db import transaction

from base.models import UserStoreLink, Store, UserStoreLink, User,Subscription

@shared_task
def sleepy(duration):
    sleep(duration)
    return None

@shared_task(acks_late=True)
def send_email_task(numbers, msg, store_id):
    try:
        store = Store.objects.get(id=store_id)
    except Store.DoesNotExist:
        print(f"Store with id {store_id} does not exist.")
        return None

    messages_limit = store.subscription.messages_limit
    sent_count = 0

    for number in numbers:
        if store.message_count >= messages_limit:
            print(f"Message limit reached: {store.message_count} messages sent.")
            break

        # Simulate sending message
        print(f"Sending email to {number} with message: {msg}")
        sent_count += 1

        # Update message count atomically
        with transaction.atomic():
            store.message_count += 1
            store.save(update_fields=['message_count'])

    print(f"Total messages sent: {sent_count}")
    return None