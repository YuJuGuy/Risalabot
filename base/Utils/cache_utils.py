from django.core.cache import cache
from base.models import Store, UserStoreLink, StaticBot, StaticBotStart, Subscription, StaticBotLog, Campaign, User, Notification, MessagesSent
import logging

logger = logging.getLogger(__name__)

CACHE_TIMEOUT = 60 * 5  # Cache for 5 minutes

def get_store_by_id(store_id):
    cache_key = f"store_{store_id}"
    store = cache.get(cache_key)
    if not store:
        store = Store.objects.filter(store_id=store_id).first()
        if store:
            cache.set(cache_key, store, CACHE_TIMEOUT)
            logger.info(f"store: {store}")
    return store

def get_user_by_store_id(store_id):
    cache_key = f"user_{store_id}"
    user = cache.get(cache_key)
    if not user:
        storelinke = UserStoreLink.objects.filter(store__store_id=store_id).first()
        user = storelinke.user
        if user:
            cache.set(cache_key, user, CACHE_TIMEOUT)
            logger.info(f"user: {user}")
    return user


def get_subscription(store_id):
    cache_key = f"subscription_{store_id}"
    subscription = cache.get(cache_key)
    if not subscription:
        subscription = Subscription.objects.filter(store__store_id=store_id).first()
        if subscription:
            cache.set(cache_key, subscription, CACHE_TIMEOUT)
            logger.info(f"subscription: {subscription}")
    return subscription

def get_user_store_link(store_id):
    cache_key = f"user_store_link_{store_id}"
    user_store_link = cache.get(cache_key)
    if not user_store_link:
        user_store_link = UserStoreLink.objects.select_related('user').filter(store__store_id=store_id).first()
        if user_store_link:
            cache.set(cache_key, user_store_link, CACHE_TIMEOUT)
            logger.info(f"user_store_link: {user_store_link}")
    return user_store_link

def get_staticbot_start(store):
    cache_key = f"staticbot_start_{store.id}"
    staticbotstart = cache.get(cache_key)
    if not staticbotstart:
        staticbotstart = StaticBotStart.objects.filter(store=store).first()
        if staticbotstart:
            cache.set(cache_key, staticbotstart, CACHE_TIMEOUT)
            logger.info(f"staticbotstart: {staticbotstart}")
    return staticbotstart

def get_staticbots(store):
    cache_key = f"staticbots_{store.id}"
    staticbots = cache.get(cache_key)
    if not staticbots:
        staticbots = list(StaticBot.objects.filter(store=store))
        cache.set(cache_key, staticbots, CACHE_TIMEOUT)
        logger.info(f"staticbots: {staticbots}")
    return staticbots

def get_session(user):
    cache_key = f"session_{user.id}"
    session = cache.get(cache_key)
    if not session:
        session = user.session_id
        logger.info(f"session: {session}")
    return session

def get_campaign_by_id(campaign_id):
    cache_key = f"campaign_{campaign_id}"
    campaign = cache.get(cache_key)
    if not campaign:
        campaign = Campaign.objects.get(id=campaign_id)
        if campaign:
            cache.set(cache_key, campaign, CACHE_TIMEOUT)
            logger.info(f"campaign: {campaign}")
    return campaign


def get_recent_log(number, store, time):
    cache_key = f"recent_log_{store.id}_{time}"
    recent_log = cache.get(cache_key)
    if not recent_log:
        recent_log = StaticBotLog.objects.filter(
            customer=number,
            store=store,
            time__gte=time  # Within the last `hours`
        ).exists()

        if recent_log:
            cache.set(cache_key, recent_log, CACHE_TIMEOUT)
            logger.info(f"recent_log: {recent_log}")
    return recent_log

def get_messages_sent(store):
    cache_key = f"messages_sent_{store.id}"
    messages_sent = cache.get(cache_key)
    if not messages_sent:
        messages = MessagesSent.objects.filter(store=store).select_related('store').order_by('-created_at')
        messages_sent = [
            {
                'message': message.message,
                'to': message.to_number,
                'created_at': message.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            }
            for message in messages
        ]
        cache.set(cache_key, messages_sent, CACHE_TIMEOUT)
    return messages_sent