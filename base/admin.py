from django.contrib import admin
from .models import User, Subscription, Store, UserStoreLink, UserEvent, EventType, Campaign, FlowActionTypes, Flow, FlowStep, SuggestedFlow, SuggestedFlowStep, Trigger, TextConfig, TimeDelayConfig, SuggestedTextConfig, SuggestedTimeDelayConfig
# Register your models here.

admin.site.register(User)
admin.site.register(Subscription)
admin.site.register(Store)
admin.site.register(UserStoreLink)
admin.site.register(UserEvent)
admin.site.register(EventType)
admin.site.register(Campaign)
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

