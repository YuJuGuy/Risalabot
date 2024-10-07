from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import json
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator

# Create your models here.

class User(AbstractUser):
    email = models.EmailField(max_length=200, unique=True)
    session_id = models.CharField(max_length=200, unique=True, null=True)
    connected = models.BooleanField(default=False)
    
    
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
    subscription_date = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.store_name + ' - ' + self.store_id
    
class UserStoreLink(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f'{self.user.email} : {self.store.store_name} : {self.store.store_id}'

class Campaign(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    task_id = models.CharField(max_length=255, blank=True, null=True)
    scheduled_time = models.DateTimeField()
    status = models.CharField(max_length=20, default='draft')  # 'draft', 'scheduled', 'sent', 'cancelled', etc.
    clicks = models.IntegerField(default=0)
    purchases = models.IntegerField(default=0)
    msg = models.TextField()  # Assuming msg is text content
    customers_group = models.CharField(max_length=255)  # Changed field to store the selected group

    def __str__(self):
        return self.name
    
    
        
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
    

class Trigger(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


class Flow(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='flows')
    name = models.CharField(max_length=255)  # Flow name
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, default='draft') 
    trigger = models.ForeignKey('Trigger', on_delete=models.CASCADE, related_name='flows')  # Trigger is required (not nullable)
    reciepients = models.IntegerField(default=0)     # add number of people who have gone through the flow

    def __str__(self):
        return self.name


class FlowActionTypes(models.Model):
    name = models.CharField(max_length=255)  # Internal name like 'sms', 'email'
    label = models.CharField(max_length=255)  # Display name like 'Send SMS', 'Send Email'
    description = models.TextField(blank=True, null=True)  # Optional description
    

    def __str__(self):
        return self.label


class FlowStep(models.Model):
    flow = models.ForeignKey(Flow, on_delete=models.CASCADE, related_name='steps')
    order = models.PositiveIntegerField(validators=[MinValueValidator(1)])  # Order must be 1 or above
    action_type = models.ForeignKey(FlowActionTypes, on_delete=models.CASCADE)
    next_step = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['flow', 'order'], name='unique_order_per_flowstep')  # Unique name for FlowStep
        ]

    def save(self, *args, **kwargs):
        # Ensure that the step only has one config (either TextConfig or TimeDelayConfig)
        if hasattr(self, 'text_config') and hasattr(self, 'time_delay_config'):
            raise ValidationError("A FlowStep cannot have both TextConfig and TimeDelayConfig.")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"FlowStep in {self.flow.name} - Step {self.order}"

    
class SuggestedFlow(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    trigger = models.ForeignKey('Trigger', on_delete=models.CASCADE, related_name='suggested_flows')  # Associate trigger with suggested flow
    img = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return self.name

class SuggestedFlowStep(models.Model):
    suggested_flow = models.ForeignKey(SuggestedFlow, on_delete=models.CASCADE, related_name='steps')
    order = models.PositiveIntegerField(validators=[MinValueValidator(1)])  # Order must be 1 or above
    action_type = models.ForeignKey(FlowActionTypes, on_delete=models.CASCADE)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['suggested_flow', 'order'], name='unique_order_per_suggestedflowstep')  # Unique name for SuggestedFlowStep
        ]

    def save(self, *args, **kwargs):
        # Ensure that the step only has one config (either SuggestedTextConfig or SuggestedTimeDelayConfig)
        if hasattr(self, 'suggested_text_config') and hasattr(self, 'suggested_time_delay_config'):
            raise ValidationError("A SuggestedFlowStep cannot have both SuggestedTextConfig and SuggestedTimeDelayConfig.")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"SuggestedFlowStep in {self.suggested_flow.name} - Step {self.order}"
    
class TextConfig(models.Model):
    flow_step = models.OneToOneField(FlowStep, on_delete=models.CASCADE, related_name='text_config', limit_choices_to={
        'time_delay_config__isnull': True  # Only show steps that don't have a TimeDelayConfig
    })
    message = models.TextField()

    def __str__(self):
        return f"TextConfig for {self.flow_step.flow.name} - Step {self.flow_step.order}"


class TimeDelayConfig(models.Model):
    flow_step = models.OneToOneField(FlowStep, on_delete=models.CASCADE, related_name='time_delay_config', limit_choices_to={
        'text_config__isnull': True  # Only show steps that don't have a TextConfig
    })
    delay_time = models.PositiveIntegerField()  # Delay in hours or days
    delay_type = models.CharField(max_length=50, choices=[('hours', 'Hours'), ('days', 'Days')])

    def __str__(self):
        return f"TimeDelayConfig for {self.flow_step.flow.name} - Step {self.flow_step.order}"


class SuggestedTextConfig(models.Model):
    suggested_flow_step = models.OneToOneField(SuggestedFlowStep, on_delete=models.CASCADE, related_name='suggested_text_config', limit_choices_to={
        'suggested_time_delay_config__isnull': True  # Only show steps that don't have a SuggestedTimeDelayConfig
    })
    message = models.TextField()

    def __str__(self):
        return f"Suggested TextConfig for {self.suggested_flow_step.suggested_flow.name} - Step {self.suggested_flow_step.order}"


class SuggestedTimeDelayConfig(models.Model):
    suggested_flow_step = models.OneToOneField(SuggestedFlowStep, on_delete=models.CASCADE, related_name='suggested_time_delay_config', limit_choices_to={
        'suggested_text_config__isnull': True  # Only show steps that don't have a SuggestedTextConfig
    })
    delay_time = models.PositiveIntegerField()  # Delay in hours or days
    delay_type = models.CharField(max_length=50, choices=[('hours', 'Hours'), ('days', 'Days')])

    def __str__(self):
        return f"Suggested TimeDelayConfig for {self.suggested_flow_step.suggested_flow.name} - Step {self.suggested_flow_step.order}"



@receiver(post_save, sender=FlowStep)
def create_config_for_flow_step(sender, instance, created, **kwargs):
    if created:
        # Automatically create the appropriate config
        if instance.action_type.name == 'sms' and not hasattr(instance, 'text_config'):
            TextConfig.objects.create(flow_step=instance, message='Default SMS message')
        elif instance.action_type.name == 'delay' and not hasattr(instance, 'time_delay_config'):
            TimeDelayConfig.objects.create(flow_step=instance, delay_time=1, delay_type='hours')

@receiver(post_save, sender=SuggestedFlowStep)
def create_config_for_suggested_flow_step(sender, instance, created, **kwargs):
    if created:
        # Automatically create the appropriate config for suggested steps
        if instance.action_type.name == 'sms' and not hasattr(instance, 'suggested_text_config'):
            SuggestedTextConfig.objects.create(suggested_flow_step=instance, message='Default SMS message')
        elif instance.action_type.name == 'delay' and not hasattr(instance, 'suggested_time_delay_config'):
            SuggestedTimeDelayConfig.objects.create(suggested_flow_step=instance, delay_time=1, delay_type='hours')