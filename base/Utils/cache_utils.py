from django.core.cache import cache
from base.models import Store, UserStoreLink, StaticBot, StaticBotStart

CACHE_TIMEOUT = 60 * 5  # Cache for 5 minutes

def get_store_by_id(store_id):
    cache_key = f"store_{store_id}"
    store = cache.get(cache_key)
    if not store:
        store = Store.objects.filter(store_id=store_id).first()
        if store:
            cache.set(cache_key, store, CACHE_TIMEOUT)
    return store

def get_user_store_link(store_id):
    cache_key = f"user_store_link_{store_id}"
    user_store_link = cache.get(cache_key)
    if not user_store_link:
        user_store_link = UserStoreLink.objects.select_related('user').filter(store__store_id=store_id).first()
        if user_store_link:
            cache.set(cache_key, user_store_link, CACHE_TIMEOUT)
    return user_store_link

def get_staticbot_start(store):
    cache_key = f"staticbot_start_{store.id}"
    staticbotstart = cache.get(cache_key)
    if not staticbotstart:
        staticbotstart = StaticBotStart.objects.filter(store=store).first()
        if staticbotstart:
            cache.set(cache_key, staticbotstart, CACHE_TIMEOUT)
    return staticbotstart

def get_staticbots(store):
    cache_key = f"staticbots_{store.id}"
    staticbots = cache.get(cache_key)
    if not staticbots:
        staticbots = list(StaticBot.objects.filter(store=store))
        cache.set(cache_key, staticbots, CACHE_TIMEOUT)
    return staticbots
