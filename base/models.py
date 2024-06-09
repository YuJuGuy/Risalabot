from django.db import models
from django.contrib.auth.models import AbstractUser

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
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    store_name = models.CharField(max_length=255)
    store_id = models.CharField(max_length=255)
    access_token = models.CharField(max_length=255, blank=False, null=False)
    refresh_token = models.CharField(max_length=255, blank=False, null=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    subscription = models.ForeignKey(Subscription, on_delete=models.SET_NULL, null=True, blank=True)
    token_valid = models.BooleanField(default=True)

    def __str__(self):
        return self.store_name