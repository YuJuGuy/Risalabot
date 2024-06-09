from django.contrib import admin
from .models import User, Subscription, Store
# Register your models here.

admin.site.register(User)
admin.site.register(Subscription)
admin.site.register(Store)