from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import json
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
import uuid
from django.db import models, transaction

from django.utils.crypto import get_random_string
from datetime import date, timedelta



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
    token_refresh_date = models.DateTimeField(default=timezone.now)
    subscription_message_count = models.IntegerField(default=0)
    total_customers = models.IntegerField(default=0)
    total_purchases = models.IntegerField(default=0)
    total_clicks = models.IntegerField(default=0)
    total_messages_sent = models.IntegerField(default=0)
    subscription_date = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.store_name + ' - ' + self.store_id
    
class UserStoreLink(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f'{self.user.email} : {self.store.store_name} : {self.store.store_id}'
    
    
class Group(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    group_id = models.IntegerField()  # Removed unique=True
    name = models.CharField(max_length=255)

    class Meta:
        unique_together = ('store', 'group_id')  # Enforces uniqueness within each store

    def __str__(self):
        return f"{self.store.store_name} : {self.name}, {self.group_id}"

class Customer(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    customer_name = models.CharField(max_length=255)
    customer_email = models.CharField(max_length=255, blank=True, null=True)
    customer_phone = models.CharField(max_length=255)
    customer_location = models.CharField(max_length=255)
    customer_groups = models.ManyToManyField(Group, related_name='customers')
    customer_updated_at = models.DateTimeField()

    def __str__(self):
        return f'{self.store.store_name} : Customer {self.customer_name}'

@receiver(post_save, sender=Customer)
def add_to_all_customers_group(sender, instance, created, **kwargs):
    if created:  # Only add if the customer is newly created
        # Ensure the 'جميع العملاء' group exists for the customer's store
        all_customers_group, _ = Group.objects.get_or_create(
            name='جميع العملاء',
            store=instance.store,
            defaults={'group_id': int(f"1111{instance.store.store_id}")}  # Use unique ID logic as needed
        )
        
        # Use transaction.on_commit to ensure Many-to-Many relationship is added after the save
        transaction.on_commit(lambda: instance.customer_groups.add(all_customers_group))
        
        
class Campaign(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    status_choices = (
        ('draft', 'مسودة'),
        ('scheduled', 'مجدولة'),
        ('sent', 'تم الإرسال'),
        ('cancelled', 'تم الإلغاء'),
        ('failed', 'فشلت'),
        ('deleted', 'تم الحذف'),
    
    )
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    task_id = models.CharField(max_length=255, blank=True, null=True)
    scheduled_time = models.DateTimeField()
    status = models.CharField(max_length=20, default='draft')  # 'draft', 'scheduled', 'sent', 'cancelled', etc.
    clicks = models.IntegerField(default=0)
    purchases = models.IntegerField(default=0)
    msg = models.TextField()  # Assuming msg is text content
    customers_group = models.CharField(max_length=255)  # Changed field to store the selected group
    messages_sent = models.IntegerField(default=0)
    track = models.BooleanField(default=False)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.pk is not None:
            try:
                old_instance = Campaign.objects.get(pk=self.pk)
                if old_instance.status != self.status:
                    self.status_changed_at = timezone.now()
                
                # Calculate differences
                clicks_diff = self.clicks - old_instance.clicks
                messages_diff = self.messages_sent - old_instance.messages_sent
                purchases_diff = self.purchases - old_instance.purchases
                
                # Update store totals and log activity
                if messages_diff != 0:
                    self.store.subscription_message_count += messages_diff
                    self.store.total_messages_sent += messages_diff
                    self.store.save(update_fields=['subscription_message_count', 'total_messages_sent'])
                    
                    # Log message activity
                    log_activity(self.store, 'campaign', self.pk, 'message', messages_diff)
                
                if purchases_diff != 0:
                    self.store.total_purchases += purchases_diff
                    self.store.save(update_fields=['total_purchases'])
                    
                    # Log purchase activity
                    log_activity(self.store, 'campaign', self.pk, 'purchase', purchases_diff)
                
                if clicks_diff != 0:
                    self.store.total_clicks += clicks_diff
                    self.store.save(update_fields=['total_clicks'])
                    
                    # Log click activity
                    log_activity(self.store, 'campaign', self.pk, 'click', clicks_diff)
                
            except Campaign.DoesNotExist:
                self.status_changed_at = timezone.now()
        else:
            # New instance being created
            self.status_changed_at = timezone.now()
        
        super().save(*args, **kwargs)


# Helper function to handle ActivityLog increment or creation

    
    
class Trigger(models.Model):
    name = models.CharField(max_length=255)
    event_type = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


class Flow(models.Model):
    # arabic status choices
    STATUS_CHOICES = (
        ('draft', 'مسودة'),
        ('active', 'مفعلة'),
        ('paused', 'موقوفة'),
        ('archived', 'محظورة'),
        ('deleted', 'تم الحذف'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='flows')
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='flows')  # Add this line
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    status_changed_at = models.DateTimeField(null=True, blank=True)
    trigger = models.ForeignKey(Trigger, on_delete=models.CASCADE, related_name='flows')
    messages_sent = models.IntegerField(default=0)
    purchases = models.IntegerField(default=0)
    clicks = models.IntegerField(default=0)
    track = models.BooleanField(default=False)
    
    def save(self, *args, **kwargs):
        if self.pk is not None:
            try:
                old_instance = Flow.objects.get(pk=self.pk)
                if old_instance.status != self.status:
                    self.status_changed_at = timezone.now()
            
                # Calculate differences
                messages_diff = self.messages_sent - old_instance.messages_sent
                clicks_diff = self.clicks - old_instance.clicks
                purchases_diff = self.purchases - old_instance.purchases
                
                # Update store totals and log activity
                if messages_diff != 0:
                    self.store.subscription_message_count += messages_diff
                    self.store.total_messages_sent += messages_diff
                    self.store.save(update_fields=['subscription_message_count', 'total_messages_sent'])
                    
                    # Log message activity
                    log_activity(self.store, 'flow', self.pk, 'message', messages_diff)
                
                if purchases_diff != 0:
                    self.store.total_purchases += purchases_diff
                    self.store.save(update_fields=['total_purchases'])
                    
                    # Log purchase activity
                    log_activity(self.store, 'flow', self.pk, 'purchase', purchases_diff)
                
                if clicks_diff != 0:
                    self.store.total_clicks += clicks_diff
                    self.store.save(update_fields=['total_clicks'])
                    
                    # Log click activity
                    log_activity(self.store, 'flow', self.pk, 'click', clicks_diff)
                
            except Flow.DoesNotExist:
                self.status_changed_at = timezone.now()
        else:
            # New instance being created
            self.status_changed_at = timezone.now()
        
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"


class FlowActionTypes(models.Model):
    name = models.CharField(max_length=255)  # Internal name like 'sms', 'email'
    label = models.CharField(max_length=255)  # Display name like 'Send SMS', 'Send Email'
    icon = models.CharField(max_length=255, blank=True, null=True)  # Optional icon
    description = models.TextField(blank=True, null=True)  # Optional description
    

    def __str__(self):
        return self.label


class FlowStep(models.Model):
    flow = models.ForeignKey('Flow', on_delete=models.CASCADE, related_name='steps')
    order = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    action_type = models.ForeignKey(FlowActionTypes, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['flow', 'order'], name='unique_order_per_flow')
        ]

    def save(self, *args, **kwargs):
        if hasattr(self, 'text_config') + hasattr(self, 'time_delay_config') + hasattr(self, 'coupon_config') > 1:
            raise ValidationError("A FlowStep can have only one configuration.")
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
    order = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    action_type = models.ForeignKey(FlowActionTypes, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['suggested_flow', 'order'], name='unique_order_per_suggestedflowstep')
        ]

    def save(self, *args, **kwargs):
        if hasattr(self, 'suggested_text_config') + hasattr(self, 'suggested_time_delay_config') + hasattr(self, 'suggested_coupon_config') > 1:
            raise ValidationError("A SuggestedFlowStep can have only one configuration.")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"SuggestedFlowStep in {self.suggested_flow.name} - Step {self.order}"
    
    
class TextConfig(models.Model):
    flow_step = models.OneToOneField(FlowStep, on_delete=models.CASCADE, related_name='text_config', limit_choices_to={
        'time_delay_config__isnull': True, 'coupon_config__isnull': True
    })
    message = models.TextField()

    def __str__(self):
        return f"TextConfig for {self.flow_step.flow.name} - Step {self.flow_step.order}"


class TimeDelayConfig(models.Model):
    flow_step = models.OneToOneField(FlowStep, on_delete=models.CASCADE, related_name='time_delay_config', limit_choices_to={
        'text_config__isnull': True, 'coupon_config__isnull': True
    })
    delay_time = models.PositiveIntegerField()
    delay_type = models.CharField(max_length=50, choices=[('hours', 'Hours'), ('days', 'Days'), ('minutes', 'Minutes')])

    def __str__(self):
        return f"TimeDelayConfig for {self.flow_step.flow.name} - Step {self.flow_step.order}" 
    
class CouponConfig(models.Model):
    flow_step = models.OneToOneField(FlowStep, on_delete=models.CASCADE, related_name='coupon_config', limit_choices_to={
        'text_config__isnull': True, 'time_delay_config__isnull': True
    })
    type = models.CharField(max_length=50, choices=[('fixed', 'مبلغ ثابت'), ('percentage', 'نسبة مئوية')])
    amount = models.IntegerField()
    expire_in = models.IntegerField()  # Date in the format "YYYY-MM-DD"
    maximum_amount = models.IntegerField(null=True)
    free_shipping = models.BooleanField()
    exclude_sale_products = models.BooleanField()
    message = models.TextField(blank=True, null=True)


    def __str__(self):
        return f"CouponConfig for {self.flow_step.flow.name} - Step {self.flow_step.order}"

class SuggestedTextConfig(models.Model):
    suggested_flow_step = models.OneToOneField(SuggestedFlowStep, on_delete=models.CASCADE, related_name='suggested_text_config', limit_choices_to={
        'suggested_time_delay_config__isnull': True, 'suggested_coupon_config__isnull': True
    })
    message = models.TextField()

    def __str__(self):
        return f"Suggested TextConfig for {self.suggested_flow_step.suggested_flow.name} - Step {self.suggested_flow_step.order}"


class SuggestedTimeDelayConfig(models.Model):
    suggested_flow_step = models.OneToOneField(SuggestedFlowStep, on_delete=models.CASCADE, related_name='suggested_time_delay_config', limit_choices_to={
        'suggested_text_config__isnull': True, 'suggested_coupon_config__isnull': True
    })
    delay_time = models.PositiveIntegerField()
    delay_type = models.CharField(max_length=50, choices=[('hours', 'Hours'), ('days', 'Days'), ('minutes', 'Minutes')])

    def __str__(self):
        return f"Suggested TimeDelayConfig for {self.suggested_flow_step.suggested_flow.name} - Step {self.suggested_flow_step.order}"
    
class SuggestedCouponConfig(models.Model):
    suggested_flow_step = models.OneToOneField(SuggestedFlowStep, on_delete=models.CASCADE, related_name='suggested_coupon_config', limit_choices_to={
        'suggested_text_config__isnull': True, 'suggested_time_delay_config__isnull': True
    })
    type = models.CharField(max_length=50, choices=[('fixed', 'مبلغ ثابت'), ('percentage', 'نسبة مئوية')])
    amount = models.IntegerField()
    expire_in = models.IntegerField()  # Date in the format "YYYY-MM-DD"
    maximum_amount = models.IntegerField(null=True)
    free_shipping = models.BooleanField()
    exclude_sale_products = models.BooleanField()


    def __str__(self):
        return f"Suggested CouponConfig for {self.suggested_flow_step.suggested_flow.name} - Step {self.suggested_flow_step.order}"



@receiver(post_save, sender=FlowStep)
def create_config_for_flow_step(sender, instance, created, **kwargs):
    if created:
        if instance.action_type.name == 'sms' and not hasattr(instance, 'text_config'):
            TextConfig.objects.create(flow_step=instance, message='Default SMS message')
        elif instance.action_type.name == 'delay' and not hasattr(instance, 'time_delay_config'):
            TimeDelayConfig.objects.create(flow_step=instance, delay_time=1, delay_type='hours')
        elif instance.action_type.name == 'coupon' and not hasattr(instance, 'coupon_config'):
            CouponConfig.objects.create(flow_step=instance, amount=10, type='fixed', expire_in=3, maximum_amount=10, free_shipping=True, exclude_sale_products=True)


@receiver(post_save, sender=SuggestedFlowStep)
def create_config_for_suggested_flow_step(sender, instance, created, **kwargs):
    if created:
        if instance.action_type.name == 'sms' and not hasattr(instance, 'suggested_text_config'):
            SuggestedTextConfig.objects.create(suggested_flow_step=instance, message='Default SMS message')
        elif instance.action_type.name == 'delay' and not hasattr(instance, 'suggested_time_delay_config'):
            SuggestedTimeDelayConfig.objects.create(suggested_flow_step=instance, delay_time=1, delay_type='hours')
        elif instance.action_type.name == 'coupon' and not hasattr(instance, 'suggested_coupon_config'):
            SuggestedCouponConfig.objects.create(suggested_flow_step=instance, amount=10, type='fixed', expire_in=3, maximum_amount=10, free_shipping=True, exclude_sale_products=True)
            
            
class ActivityLog(models.Model):
    ACTIVITY_TYPE_CHOICES = [
        ('message', 'رسائل'),
        ('purchase', 'مشتريات'),
        ('click', 'ضغطات'),
    ]
    SOURCE_TYPE_CHOICES = [
        ('flow', 'الأتمتة'),
        ('campaign', 'الحملة'),
    ]

    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='activity_logs')
    source_type = models.CharField(max_length=10, choices=SOURCE_TYPE_CHOICES)
    source_id = models.UUIDField()  # ID of the Flow or Campaign
    activity_type = models.CharField(max_length=10, choices=ACTIVITY_TYPE_CHOICES)
    date = models.DateField()  # Track by day only
    count = models.IntegerField(default=0)  # Count of the activity (e.g., messages sent, clicks, purchases)
    user_ip = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"{self.store.store_name} - {self.get_activity_type_display()} on {self.date}"



def log_activity(store, source_type, source_id, activity_type, diff_count):
    today = date.today()
    
    # Update or create ActivityLog with count increment
    activity_log, created = ActivityLog.objects.get_or_create(
        store=store,
        source_type=source_type,
        source_id=source_id,
        activity_type=activity_type,
        date=today,
        defaults={'count': diff_count},
    )
    
    if not created:
        # If the log entry already exists, increment the count
        ActivityLog.objects.filter(
            store=store,
            source_type=source_type,
            source_id=source_id,
            activity_type=activity_type,
            date=today,
        ).update(count=models.F('count') + diff_count)
        

class AbandonedCart(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='abandoned_carts')
    customer_id = models.CharField(max_length=255)
    cart_id = models.CharField(max_length=255)
    flow_id = models.UUIDField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    bought = models.BooleanField(default=False)
