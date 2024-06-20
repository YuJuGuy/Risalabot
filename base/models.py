from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone

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
        return self.store_name
    
class UserStoreLink(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f'{self.user.email} : {self.store.store_name} : {self.store.store_id}'
    
class UserEvent(models.Model):
    store = models.OneToOneField(Store, on_delete=models.CASCADE)
    abandoned_cart = models.TextField(blank=True, null=True)
    order_received = models.TextField(blank=True, null=True)
    order_cancelled = models.TextField(blank=True, null=True)
    order_updated = models.TextField(blank=True, null=True)
    shipment_updated = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.store.store_name} - {self.store.store_id}"

