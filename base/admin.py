from django.contrib import admin
from .models import User, Subscription, Store, UserStoreLink, UserEvent, EventType
# Register your models here.

admin.site.register(User)
admin.site.register(Subscription)
admin.site.register(Store)
admin.site.register(UserStoreLink)
admin.site.register(UserEvent)
admin.site.register(EventType)