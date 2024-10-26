from django.contrib import admin
from .models import User, Subscription, Store, UserStoreLink, Campaign, FlowActionTypes, Flow, FlowStep, SuggestedFlow, SuggestedFlowStep, Trigger, TextConfig, TimeDelayConfig, SuggestedTextConfig, SuggestedTimeDelayConfig
# Register your models here.

admin.site.register(User)
admin.site.register(Subscription)
admin.site.register(Store)
admin.site.register(UserStoreLink)
@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ('name', 'store', 'status', 'scheduled_time', 'clicks', 'purchases')
    list_filter = ('status', 'scheduled_time')
    search_fields = ('name', 'store__store_name')
    date_hierarchy = 'scheduled_time'
    ordering = ['-scheduled_time']
admin.site.register(FlowActionTypes)
admin.site.register(Flow)
admin.site.register(FlowStep)
admin.site.register(SuggestedFlow)
admin.site.register(SuggestedFlowStep)
admin.site.register(Trigger)
admin.site.register(TextConfig)
admin.site.register(TimeDelayConfig)
admin.site.register(SuggestedTextConfig)
admin.site.register(SuggestedTimeDelayConfig)

