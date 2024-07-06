from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import json


# Create your models here.

class User(AbstractUser):
    name = models.CharField(max_length=200, null=True)
    email = models.EmailField(max_length=200, unique=True)
    
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    
class Subscription(models.Model):
    name = models.CharField(max_length=255)
    messages_limit = models.IntegerField()  # Field to store the message limit for the subscription
    description = models.TextField()

    def __str__(self):
        return self.name
    
class Store(models.Model):
    store_name = models.CharField(max_length=255)
    store_id = models.CharField(max_length=255, unique=True)
    access_token = models.CharField(max_length=255, blank=True, null=True)
    refresh_token = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    subscription = models.ForeignKey(Subscription, on_delete=models.SET_NULL, null=True, blank=True)
    token_valid = models.BooleanField(default=True)
    message_count = models.IntegerField(default=0)
    last_reset = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.store_name + ' - ' + self.store_id
    
class UserStoreLink(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f'{self.user.email} : {self.store.store_name} : {self.store.store_id}'
    
class EventType(models.Model):
    name = models.CharField(max_length=255, unique=True)
    label = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.label

class UserEvent(models.Model):
    ORDER_UPDATED_SUBCATEGORIES = [
        ('pending_payment', 'بإنتظار الدفع'),
        ('pending_review', 'بإنتظار المراجعة'),
        ('in_progress', 'قيد التنفيذ'),
        ('completed', 'تم التنفيذ'),
        ('in_delivery', 'جاري التوصيل'),
        ('delivered', 'تم التوصيل'),
        ('shipped', 'تم الشحن'),
        ('cancelled', 'ملغي'),
        ('returned', 'مسترجع'),
        ('in_return', 'قيد الإسترجاع'),
        ('quotation_requested', 'طلب عرض سعر'),
    ]

    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    event_type = models.ForeignKey(EventType, on_delete=models.CASCADE)
    subcategory = models.CharField(max_length=50, choices=ORDER_UPDATED_SUBCATEGORIES, blank=True, null=True)
    message_template = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ('store', 'event_type', 'subcategory')

    def __str__(self):
        if self.subcategory:
            return f"{self.store.store_name} - {self.store.store_id} - {self.event_type.name} - {self.get_subcategory_display()}"
        return f"{self.store.store_name} - {self.store.store_id} - {self.event_type.name}"

class Campaign(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    scheduled_time = models.DateTimeField()
    status = models.CharField(max_length=20, default='draft')  # 'draft', 'scheduled', 'sent', 'cancelled', etc.
    clicks = models.IntegerField(default=0)
    purchases = models.IntegerField(default=0)
    msg = models.TextField()  # Assuming msg is text content
    customers_group = models.CharField(max_length=255)  # Changed field to store the selected group

    def __str__(self):
        return self.name