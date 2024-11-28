from django.contrib import admin
from .models import User, Subscription, Store, UserStoreLink, Campaign, FlowActionTypes, Flow, FlowStep, SuggestedFlow, SuggestedFlowStep, Trigger, TextConfig, TimeDelayConfig, SuggestedTextConfig, SuggestedTimeDelayConfig, Customer, Group
from .models import CouponConfig, SuggestedCouponConfig, ActivityLog
from automations.models import MonthlyInstallations, MonthlyPayments, AppTrial
# Customize User model admin
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('email', 'connected', 'session_id', 'is_active')
    search_fields = ('email', 'session_id')
    list_filter = ('is_active', 'connected')
    ordering = ('email',)

# Customize Store model admin
@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ('store_name', 'store_id', 'subscription', 'created_at', 'updated_at', 'token_valid', 'total_customers', 'total_purchases', 'total_messages_sent', 'subscription_message_count')
    search_fields = ('store_name', 'store_id')
    list_filter = ('token_valid', 'subscription')
    ordering = ('-created_at',)

@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ('name', 'store', 'status', 'scheduled_time', 'clicks', 'purchases', 'messages_sent')
    list_filter = ('status', 'scheduled_time', 'store__store_name')
    search_fields = ('name', 'store__store_name')
    date_hierarchy = 'scheduled_time'
    ordering = ['-scheduled_time']
    actions = ['mark_as_sent']

    def mark_as_sent(self, request, queryset):
        updated = queryset.update(status='sent')
        self.message_user(request, f"{updated} campaigns marked as sent.")

    mark_as_sent.short_description = "Mark selected campaigns as sent"

@admin.register(Flow)
class FlowAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'store', 'status', 'messages_sent', 'purchases')
    list_filter = ('status', 'store__store_name')
    search_fields = ('name', 'owner__email', 'store__store_name')
    ordering = ['-created_at']
    date_hierarchy = 'created_at'

@admin.register(FlowStep)
class FlowStepAdmin(admin.ModelAdmin):
    list_display = ('flow', 'order', 'action_type')
    list_filter = ('flow__name', 'action_type__name')
    search_fields = ('flow__name',)

# Customize Suggested Flow admin
@admin.register(SuggestedFlow)
class SuggestedFlowAdmin(admin.ModelAdmin):
    list_display = ('name', 'trigger', 'description')
    search_fields = ('name', 'trigger__name')

@admin.register(SuggestedFlowStep)
class SuggestedFlowStepAdmin(admin.ModelAdmin):
    list_display = ('suggested_flow', 'order', 'action_type')
    search_fields = ('suggested_flow__name', 'action_type__name')

# Simplified Trigger admin
@admin.register(Trigger)
class TriggerAdmin(admin.ModelAdmin):
    list_display = ('name', 'event_type', 'description')
    search_fields = ('name', 'event_type')

@admin.register(MonthlyInstallations)
class MonthlyInstallationsAdmin(admin.ModelAdmin):
    list_display = ('store', 'date')
    search_fields = ('store__store_name', 'date')
    ordering = ('-date',)

@admin.register(MonthlyPayments)
class MonthlyPaymentsAdmin(admin.ModelAdmin):
    list_display = ('store', 'date')
    search_fields = ('store__store_name', 'date')
    ordering = ('-date',)

@admin.register(AppTrial)
class AppTrialAdmin(admin.ModelAdmin):
    list_display = ('store', 'date', 'reference_number')
    search_fields = ('store__store_name', 'reference_number')
    
    
admin.site.register(Customer)
admin.site.register(Group)
admin.site.register(Subscription)
admin.site.register(UserStoreLink)
admin.site.register(FlowActionTypes)
admin.site.register(TextConfig)
admin.site.register(TimeDelayConfig)
admin.site.register(SuggestedTextConfig)
admin.site.register(SuggestedTimeDelayConfig)
admin.site.register(CouponConfig)
admin.site.register(SuggestedCouponConfig)
admin.site.register(ActivityLog)



admin.site.site_header = "Risalabot Admin"
admin.site.site_title = "Risalabot Admin Portal"
admin.site.index_title = "Welcome to Risalabot Admin Portal"
