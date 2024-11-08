from celery import shared_task, chain
import requests
from django.db import transaction
from base.apis import create_coupon, get_customer_count, store_refresh_token
from datetime import datetime, timedelta, timezone
from django.utils.crypto import get_random_string
from base.models import Store, Campaign, UserStoreLink, Flow, FlowStep, TextConfig, TimeDelayConfig, CouponConfig
import logging


logging.basicConfig(level=logging.INFO)



@shared_task
def update_store_customers(store_id):
    store = Store.objects.get(id=store_id)
    store_link = UserStoreLink.objects.filter(store=store).first()
    if not store_link:
        logging.error(f"No UserStoreLink found for store {store.store_id}")
        return
    
    customer_count = get_customer_count(store_link.user)
    if customer_count['success']:
        with transaction.atomic():
            store.total_customers = customer_count['customer_count']
            store.save(update_fields=['total_customers'])
            logging.info(f"Updated total customers for store {store.store_id} to {store.total_customers}")
    else:
        logging.error(f"Failed to update total customers for store {store.store_id}: {customer_count['message']}")



@shared_task
def update_total_customers(batch_size=10):
    stores = Store.objects.all()
    # Split stores into batches
    batches = [stores[i:i + batch_size] for i in range(0, len(stores), batch_size)]

    for batch in batches:
        for store in batch:
            logging.info(f"Updating total customers for store {store.store_id}")
            update_store_customers.delay(store.id)  # Schedule each store update as an individual task
        
        # Optional: Sleep between batches to avoid overloading the system
        recurring_refresh.apply_async(countdown=60)  # Schedule the next batch after a 1-minute delay
        
@shared_task
def reset_monthly_quota(store_id):
    store = Store.objects.get(id=store_id)
    time_since_insertion = datetime.now(timezone.utc) - store.subscription_date
    try:
        if time_since_insertion >= timedelta(days=30):
            with transaction.atomic():
                store.subscription_message_count = 0
                store.subscription_date = datetime.now(timezone.utc)
                store.save(update_fields=['subscription_date', 'subscription_message_count'])
                logging.info(f"Updated subscription for store {store.id} to {store.subscription_message_count} at {store.subscription_date}")
            return True, "Successfully Updated"
        else:
            logging.info(f"Period less than 30 days at {datetime.now(timezone.utc)}. Customer store date {store.subscription_date}")
            return True, "Still not 30 days"
    except Exception as e:
        logging.error(f"Error occurred when updating store {store_id}: {e}")
        return False, f"Error occurred when updating store {store_id}: {e}"


@shared_task
def update_store_subscription(batch_size=10):
    stores = Store.objects.all()
    batches = [stores[i:i + batch_size] for i in range(0, len(stores), batch_size)]

    for batch in batches:
        for store in batch:
            task = reset_monthly_quota.apply_async(args=[store.id])  # Schedule with apply_async to check results later
            task_result = task.get(timeout=10)  # Adjust timeout if needed

            success, message = task_result
            if success:
                logging.info(f"Successfully updated subscription for store {store.id}: {message}")
            else:
                logging.error(f"Failed to update subscription for store {store.id}: {message}")

        # Optionally, delay the next batch to avoid overloading
        recurring_refresh.apply_async(countdown=60)  # Schedule the next batch after a 1-minute delay
        
        
@shared_task
def recurring_refresh(batch_size=10):
    stores = Store.objects.all()
    batches = [stores[i:i + batch_size] for i in range(0, len(stores), batch_size)]

    for batch in batches:
        for store in batch:
            if datetime.now(timezone.utc) - store.token_refresh_date > timedelta(days=10):
                result = store_refresh_token(store.store_id)
                if result['success']:
                    logging.info(f"Successfully updated access and refresh tokens for store {store.store_id}")
                else:
                    logging.error(f"Failed to update access and refresh tokens for store {store.store_id}: {result['message']}")

        # Optionally, delay the next batch to avoid overloading
        recurring_refresh.apply_async(countdown=60)  # Schedule the next batch after a 1-minute delay

            
