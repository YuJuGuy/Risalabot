from celery import shared_task, chain
import requests
import time

from django.db import transaction
from base.apis import create_coupon, get_customer_count, store_refresh_token
from datetime import datetime, timedelta, timezone
from django.utils.crypto import get_random_string
from base.models import Store, Campaign, UserStoreLink, Flow, FlowStep, TextConfig, TimeDelayConfig, CouponConfig
import logging


logging.basicConfig(level=logging.INFO)



@shared_task
def update_store_customers(store_id):
    """
    Updates the total customers for a specific store.
    """
    store = Store.objects.get(id=store_id)
    store_link = UserStoreLink.objects.filter(store=store).first()
    if not store_link:
        logging.error(f"No UserStoreLink found for store {store.store_id}")
        return

    # Fetch customer count from API
    customer_count = get_customer_count(store_link.user)
    if customer_count['success']:
        # Atomic save to prevent partial updates
        with transaction.atomic():
            store.total_customers = customer_count['customer_count']
            store.save(update_fields=['total_customers'])
            logging.info(f"Updated total customers for store {store.store_id} to {store.total_customers}")
    else:
        logging.error(f"Failed to update total customers for store {store.store_id}: {customer_count['message']}")


@shared_task
def update_total_customers(batch_size=10, delay_between_batches=60):
    """
    Updates total customers for all stores in batches.
    Each batch waits for `delay_between_batches` seconds before proceeding to the next.
    """
    stores = Store.objects.all()
    batches = [stores[i:i + batch_size] for i in range(0, len(stores), batch_size)]

    for index, batch in enumerate(batches):
        for store in batch:
            logging.info(f"Scheduling total customer update for store {store.store_id}")
            update_store_customers.delay(store.id)  # Schedule each store update as an individual task
        
        # Schedule the next batch with a delay using countdown
        if index < len(batches) - 1:  # Don't schedule delay for the last batch
            logging.info(f"Batch {index + 1} completed, scheduling next batch after {delay_between_batches} seconds.")
            update_total_customers.apply_async(args=[batch_size, delay_between_batches], countdown=delay_between_batches)

        
        
@shared_task
def reset_monthly_quota(store_id):
    """
    Resets the monthly quota for a store if 30 days have passed since the last reset.
    """
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
def update_store_subscription(batch_size=10, delay_between_batches=60):
    """
    Updates store subscriptions in batches.
    Each batch waits for `delay_between_batches` seconds before proceeding to the next.
    """
    stores = Store.objects.all()
    batches = [stores[i:i + batch_size] for i in range(0, len(stores), batch_size)]

    for index, batch in enumerate(batches):
        for store in batch:
            task = reset_monthly_quota.apply_async(args=[store.id])  # Schedule with apply_async to check results later
            task_result = task.get(timeout=10)  # Adjust timeout if needed

            success, message = task_result
            if success:
                logging.info(f"Successfully updated subscription for store {store.id}: {message}")
            else:
                logging.error(f"Failed to update subscription for store {store.id}: {message}")
        
        # Schedule the next batch with a delay using countdown
        if index < len(batches) - 1:  # Don't schedule delay for the last batch
            logging.info(f"Batch {index + 1} completed, scheduling next batch after {delay_between_batches} seconds.")
            update_store_subscription.apply_async(args=[batch_size, delay_between_batches], countdown=delay_between_batches)



@shared_task
def recurring_refresh(batch_size=10, delay_between_batches=60):
    """
    Refreshes tokens for stores if the last refresh was more than 10 days ago.
    Processes stores in batches and waits between batches to control API usage.
    """
    stores = Store.objects.all()
    batches = [stores[i:i + batch_size] for i in range(0, len(stores), batch_size)]

    for index, batch in enumerate(batches):
        for store in batch:
            # Check if token needs to be refreshed
            if datetime.now(timezone.utc) - store.token_refresh_date > timedelta(days=10):
                result = store_refresh_token(store.store_id)
                if result['success']:
                    logging.info(f"Successfully updated access and refresh tokens for store {store.store_id}")
                else:
                    logging.error(f"Failed to update access and refresh tokens for store {store.store_id}: {result['message']}")
            else:
                logging.info(f"Token for store {store.store_id} is still valid, no refresh needed.")
        
        # Schedule the next batch with a delay using countdown, except for the last batch
        if index < len(batches) - 1:  # Don't schedule delay for the last batch
            logging.info(f"Batch {index + 1} completed, scheduling next batch after {delay_between_batches} seconds.")
            recurring_refresh.apply_async(args=[batch_size, delay_between_batches], countdown=delay_between_batches)



            
