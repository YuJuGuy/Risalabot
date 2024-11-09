from django.shortcuts import render,redirect
from django.contrib.auth import authenticate
from celery.exceptions import CeleryError
from django.core.exceptions import PermissionDenied
from django.contrib import messages
from django.db import transaction
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.utils.timezone import make_aware
from . forms import CreateUserForm, CampaignForm, GroupCreationForm, FlowForm
from . models import User, Store, UserStoreLink,Trigger, Campaign, FlowActionTypes, Flow, FlowStep, SuggestedFlow, SuggestedFlowStep, TextConfig, TimeDelayConfig,SuggestedTextConfig, SuggestedTimeDelayConfig, Customer, Group, CouponConfig, SuggestedCouponConfig
from django.http import JsonResponse
from automations.tasks import send_whatsapp_message_task
from . apis import get_customer_data, create_customer_group, delete_customer_group,group_campaign, get_customers_from_group
from django.utils.crypto import get_random_string
from Risalabot.celery import app as celery_app
from datetime import datetime
from django.db.models import F
from django.shortcuts import get_object_or_404
import json
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.db import IntegrityError
from datetime import datetime, timezone, timedelta
from . decorators import check_token_validity


import logging

logger = logging.getLogger(__name__)


__all__ = ('celery_app',) 





def home(request):
    return render(request, 'base/home.html')


def loginPage(request):
    page = 'login'
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        email = request.POST.get('email').lower()
        password = request.POST.get('password')

        try:
            user = User.objects.get(email=email)
        except:
            messages.error(request, 'User does not exist')

        user = authenticate(request, email=email, password=password)

        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, 'Email OR password does not exit')

    context = {'page': page}
    return render(request, 'base/login_register.html', context)

def logoutUser(request):
    logout(request)
    return redirect('login')

def generate_unique_session_id():
    """Generate a unique session_id for the user."""
    while True:
        session_id = get_random_string(length=32)
        if not User.objects.filter(session_id=session_id).exists():
            return session_id

def registerPage(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    form = CreateUserForm()

    if request.method == 'POST':
        form = CreateUserForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.username = user.username.lower()
            user.session_id = generate_unique_session_id()
            user.save()
            login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, 'An error occurred during registration')

    return render(request, 'base/login_register.html', {'form': form})


@login_required(login_url='login')
@check_token_validity
def dashboard(request, context=None):
    # Initialize default values
    if context is None:
        context = {}
    
    context.update({
        'store': None,
        'message_count': 0,
        'purchases': 0,
        'total_customers': 0,
        'active_automations': 0,
        'clicks': 0
    })

    try:
        # Get store data if it exists
        store_link = UserStoreLink.objects.select_related('store').get(user=request.user)
        store = store_link.store

        # Update context with store data
        context.update({
            'store': store,
            'message_count': store.total_messages_sent,
            'purchases': store.total_purchases,
            'total_customers': store.total_customers,
            'clicks': store.total_clicks,
            'active_automations': Flow.objects.filter(owner=request.user, status='active').count() + Campaign.objects.filter(store=store, status='scheduled').count()
        })
    except UserStoreLink.DoesNotExist:
        logger.error(f"No store linked to your account")
    except Exception as e:
        logger.error(f"Error in dashboard view: {str(e)}")
        messages.error(request, 'An error occurred while loading dashboard data.')
    
    return render(request, 'base/dashboard.html', context)


# @login_required(login_url='login')
# def manage_event(request, event_id=None):
#     try:
#         store = UserStoreLink.objects.get(user=request.user).store
#         events = UserEvent.objects.filter(store=store)
#     except UserStoreLink.DoesNotExist:
#         messages.error(request, 'No store linked. Please link a store first.')
#         return redirect('dashboard')
    
#     event = None
#     if event_id:
#         event = UserEvent.objects.get(id=event_id, store=UserStoreLink.objects.get(user=request.user).store)

#     if request.method == 'POST':
#         form = UserEventForm(request.POST, instance=event)
#         if form.is_valid():
#             event_type = form.cleaned_data['event_type']
#             subcategory = form.cleaned_data['subcategory']
            
#             if UserEvent.objects.filter(store=store, event_type=event_type, subcategory=subcategory).exclude(id=event_id).exists():
#                 messages.error(request, 'You have already created an event for this type and subcategory.')
#             else:
#                 event = form.save(commit=False)
#                 event.store = store
#                 event.save()
#                 if event_id:
#                     messages.success(request, 'Event updated successfully.')
#                 else:
#                     messages.success(request, 'Event created successfully.')
#             return redirect('events')
#         else:
#             messages.error(request, 'Error saving event. Please correct the form errors.')
#     else:
#         form = UserEventForm(instance=event)

#     try:
#         order_updated_event_type = EventType.objects.get(name='order.updated')
#         order_updated_event_type_id = order_updated_event_type.id
#     except EventType.DoesNotExist:
#         order_updated_event_type_id = None

#     context = {
#         'events': events,
#         'form': form,
#         'event': event,
#         'order_updated_event_type_id': order_updated_event_type_id,
#     }
#     return render(request, 'base/events.html', context)



# @login_required(login_url='login')
# def delete_event(request, event_id):
#     event = UserEvent.objects.get(id=event_id, store=UserStoreLink.objects.get(user=request.user).store)
#     event.delete()
#     messages.success(request, 'Event deleted successfully.')
#     return redirect('events')


@login_required(login_url='login')
@check_token_validity
def flows(request, context=None):
    try:
        user = request.user
    except User.DoesNotExist:
        messages.error(request, 'No user found.')
        return redirect('dashboard')
    
    if context is None:
        context = {}
    
    if request.method == 'POST':
        form = FlowForm(request.POST)
        if form.is_valid():
            # Save the form but don't commit yet, as we need to add the owner
            new_flow = form.save(commit=False)
            new_flow.owner = request.user  # Associate the flow with the current user
            new_flow.store = UserStoreLink.objects.get(user=request.user).store
            new_flow.save()  # Now save the flow
            messages.success(request, 'Flow created successfully.')
            return redirect('flow', flow_id=new_flow.id)  # Redirect to the flow builder
        else:
            messages.error(request, 'Error creating flow. Please correct the form errors.')
            return redirect('flows')
    else:
        form = FlowForm()
    
    
    context.update({
        'form': form,
        'triggers': Trigger.objects.all(),
    })
    return render(request, 'base/flows.html', context)


@login_required(login_url='login')
def get_flows(request):
    try:
        user = request.user
        flows = list(user.flows.all().values('id', 'name', 'updated_at', 'status', 'messages_sent','purchases'))
        for flow in flows:
            flow['status'] = dict(Flow.STATUS_CHOICES).get(flow['status'], flow['status'])
        for flow in flows:
            flow['updated_at'] = flow['updated_at'].strftime('%Y-%m-%d %H:%M')
        suggestions = list(SuggestedFlow.objects.all().values('id', 'name', 'description', 'img'))
        data = {
            'flows': flows,
            'suggestions': suggestions
        }
        return JsonResponse(data)
        
    except User.DoesNotExist:
        messages.error(request, 'No user found.')
        return redirect('dashboard')
    

    
def validate_steps_data(steps_data):
        """Validates the steps data sent as JSON."""
        try:
            steps = json.loads(steps_data)
        except json.JSONDecodeError:
            raise ValidationError("Invalid steps data format. Ensure the data is valid JSON.")

        # Check if the steps_data is a list
        if not isinstance(steps, list):
            raise ValidationError("Steps data should be a list.")

        valid_action_types = FlowActionTypes.objects.values_list('name', flat=True)
        
        # Validate each step's structure and content
        for step in steps:
            if 'action_type' not in step or step['action_type'] not in valid_action_types:
                raise ValidationError(f"Invalid action type: {step.get('action_type')}")

            # SMS action validation
            if step['action_type'] == 'sms':
                message = step.get('content', {}).get('message', '').strip()
                if not message:
                    raise ValidationError("SMS action requires a message.")

            # Delay action validation
            elif step['action_type'] == 'delay':
                delay_time = step.get('content', {}).get('delay_time')
                delay_type = step.get('content', {}).get('delay_type')

                if not delay_time or not str(delay_time).isdigit():
                    raise ValidationError("Delay action requires a valid delay time.")

                if delay_type not in ['hours', 'days', 'minutes']:
                    raise ValidationError("Invalid delay type. Choose either 'hours' or 'days'.")
                
                
            # Coupon action validation
            elif step['action_type'] == 'coupon':
                coupon_type = step.get('content', {}).get('type')
                amount = step.get('content', {}).get('amount')
                expire_in = step.get('content', {}).get('expire_in')
                maximum_amount = step.get('content', {}).get('maximum_amount')
                free_shipping = step.get('content', {}).get('free_shipping')
                exclude_sale_products = step.get('content', {}).get('exclude_sale_products')

                if coupon_type not in ['fixed', 'percentage']:
                    raise ValidationError("Invalid coupon type. Choose either 'fixed' or 'percentage'.")

                if amount is None or amount <= 0:
                    raise ValidationError("Coupon action requires a valid amount.")

                if expire_in is None or expire_in <= 0:
                    raise ValidationError("Coupon action requires a valid expiration period.")

                if maximum_amount is not None and maximum_amount < 0:
                    raise ValidationError("Maximum amount cannot be negative.")

                if free_shipping not in [True, False]:
                    raise ValidationError("Free shipping must be a boolean value.")

                if exclude_sale_products not in [True, False]:
                    raise ValidationError("Exclude sale products must be a boolean value.")
        
        return steps
    
@login_required(login_url='login')
@require_http_methods(["GET", "POST"])
@check_token_validity
def flow_builder(request, flow_id, context=None):
    try:
        flow = Flow.objects.get(id=flow_id, owner=request.user)
    except Flow.DoesNotExist:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'errors': 'Flow not found.'}, status=404)
        messages.error(request, 'Flow not found.')
        return redirect('flows')

    if context is None:
        context = {}
    if request.method == 'POST':
        flow_form = FlowForm(request.POST, instance=flow)
        if flow_form.is_valid():
            steps_data = request.POST.get('steps', '')
            print(steps_data)
            

            
            try:
                steps = validate_steps_data(steps_data)
            except ValidationError as e:
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'errors': str(e)}, status=400)
                messages.error(request, f"Steps validation error: {e}")
                return redirect('flow', flow_id=flow_id)
            
            if not steps and request.POST.get('status') == 'active':
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'errors': 'You need to add at least one message.'}, status=400)
                messages.error(request, 'You need to add at least one message.')
                return redirect('flow', flow_id=flow_id)
            
            try:
                with transaction.atomic():
                    flow_form.save()
                    FlowStep.objects.filter(flow=flow).update(order=F('order') + 1000)

                    existing_steps_ids = []
                    for index, step_data in enumerate(steps, start=1):
                        step_id = step_data.get('step_id')
                        action_type = step_data['action_type']
                        status = step_data['status']
                        content = step_data.get('content', {})

                        if step_id:
                            step = get_object_or_404(FlowStep, id=step_id, flow=flow)
                            step.order = index
                            action_type_obj = get_object_or_404(FlowActionTypes, name=action_type)
                            if step.action_type != action_type_obj:
                                TextConfig.objects.filter(flow_step=step).delete()
                                TimeDelayConfig.objects.filter(flow_step=step).delete()
                                CouponConfig.objects.filter(flow_step=step).delete()
                                step.action_type = action_type_obj
                            step.save()
                        else:
                            action_type_obj = get_object_or_404(FlowActionTypes, name=action_type)
                            step = FlowStep.objects.create(
                                flow=flow,
                                order=index,
                                action_type=action_type_obj
                            )

                        if action_type == 'sms':
                            if not content.get('message'):
                                raise ValidationError('SMS action requires a message.')
                            TimeDelayConfig.objects.filter(flow_step=step).delete()
                            TextConfig.objects.update_or_create(
                                flow_step=step,
                                defaults={'message': content.get('message', '')}
                            )
                        elif action_type == 'delay':
                            if not content.get('delay_time') or not str(content.get('delay_time')).isdigit():
                                raise ValidationError('Delay action requires a valid delay time.')
                            if content.get('delay_type') not in ['hours', 'days', 'minutes']:
                                raise ValidationError('Invalid delay type. Choose either "hours" or "days".')
                            TextConfig.objects.filter(flow_step=step).delete()
                            TimeDelayConfig.objects.update_or_create(
                                flow_step=step,
                                defaults={
                                    'delay_time': content.get('delay_time', 1),
                                    'delay_type': content.get('delay_type', 'hours')
                                }
                            )
                        elif action_type == 'coupon':
                            if not content.get('type'):
                                raise ValidationError('Coupon action requires a coupon type.')
                            if not content.get('amount') or not str(content.get('amount')).isdigit():
                                raise ValidationError('Coupon action requires a valid amount.')
                            if content.get('type') not in ['fixed', 'percentage']:
                                raise ValidationError('Invalid coupon type. Choose either "fixed" or "percentage".')
                            TextConfig.objects.filter(flow_step=step).delete()
                            max_discount = content.get('maximum_amount', None) if content.get('type') == 'fixed' else None
                            CouponConfig.objects.update_or_create(
                                flow_step=step,
                                defaults={
                                    'coupon_type': content.get('type'),
                                    'amount': content.get('amount'),
                                    'max_discount': max_discount,
                                    'expiry_days': content.get('expire_in', 0),
                                    'free_shipping': content.get('free_shipping', False),
                                    'exclude_sale_products': content.get('exclude_sale_products', False)
                                }
                            )

                        existing_steps_ids.append(step.id)

                    FlowStep.objects.filter(flow=flow).exclude(id__in=existing_steps_ids).delete()

                if FlowStep.objects.filter(flow=flow).exists():
                    flow.status = status
                    flow.save(update_fields=['status'])
                    
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'success': True, 'redirect_url': reverse('flows')})
                else:
                    return redirect('flows')
            except (ValidationError, IntegrityError, PermissionDenied) as e:
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'errors': str(e)}, status=400)
                messages.error(request, f"An error occurred while saving the flow: {str(e)}")
                return redirect('flow', flow_id=flow_id)
        else:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'errors': flow_form.errors}, status=400)
            else:
                messages.error(request, 'Form is invalid. Please correct the errors.')
                return redirect('flow', flow_id=flow_id)

    flow_steps = FlowStep.objects.filter(flow=flow).order_by('order')
    action_types = FlowActionTypes.objects.all()
    context.update({
        'flow': flow,
        'triggers': Trigger.objects.all(),
        'form': FlowForm(instance=flow),
        'flow_steps': flow_steps,
        'action_types': action_types,
        'redirect_url': reverse('flows'),
    })

    return render(request, 'base/flow_builder.html', context)


@login_required(login_url='login')
def delete_flow(request, flow_id):
    flow = get_object_or_404(Flow, id=flow_id, owner=request.user)
    flow.delete()
    messages.success(request, 'Flow deleted successfully.')
    return redirect('flows')

@login_required
def activate_suggested_flow(request, suggestion_id):
    """
    Activate a suggested flow by creating a copy for the current user.
    """
    try:
        with transaction.atomic():
            # Get the suggested flow to copy
            suggested_flow = get_object_or_404(SuggestedFlow, id=suggestion_id)
            logger.info(f"Starting to copy suggested flow {suggested_flow.id}: {suggested_flow.name}")
            
            # Create a new Flow for the current user
            new_flow = Flow.objects.create(
                owner=request.user,
                store=UserStoreLink.objects.get(user=request.user).store,
                name=suggested_flow.name,
                trigger=suggested_flow.trigger,
                status='draft'  # Always start as draft
            )
            logger.info(f"Created new flow {new_flow.id}")
            
            # Get all suggested steps ordered by their sequence
            suggested_steps = SuggestedFlowStep.objects.select_related(
                'suggested_text_config',
                'suggested_time_delay_config',
                'suggested_coupon_config'  # Added comma to fix syntax
            ).filter(
                suggested_flow=suggested_flow
            ).order_by('order')
            
            # Copy steps and their configurations
            for suggested_step in suggested_steps:
                logger.info(f"Processing step {suggested_step.id} with order {suggested_step.order}")
                
                # Create the flow step
                new_step = FlowStep.objects.create(
                    flow=new_flow,
                    order=suggested_step.order,
                    action_type=suggested_step.action_type,
                )
                logger.info(f"Created new step {new_step.id}")
                
                # Check for existing configurations before creating new ones
                existing_text_config = TextConfig.objects.filter(flow_step=new_step).exists()
                existing_delay_config = TimeDelayConfig.objects.filter(flow_step=new_step).exists()
                existing_coupon_config = CouponConfig.objects.filter(flow_step=new_step).exists()  # Check for coupon config
                
                if existing_text_config or existing_delay_config or existing_coupon_config:
                    logger.warning(f"Configuration already exists for step {new_step.id}")
                    continue
                
                try:
                    # Try to get the text config
                    text_config = SuggestedTextConfig.objects.filter(suggested_flow_step=suggested_step).first()
                    if text_config:
                        logger.info(f"Creating text config for step {new_step.id}")
                        TextConfig.objects.create(
                            flow_step=new_step,
                            message=text_config.message
                        )
                    
                    # Try to get the delay config
                    delay_config = SuggestedTimeDelayConfig.objects.filter(suggested_flow_step=suggested_step).first()
                    if delay_config:
                        logger.info(f"Creating delay config for step {new_step.id}")
                        TimeDelayConfig.objects.create(
                            flow_step=new_step,
                            delay_time=delay_config.delay_time,
                            delay_type=delay_config.delay_type
                        )
                    
                    # Try to get the coupon config
                    coupon_config = SuggestedCouponConfig.objects.filter(suggested_flow_step=suggested_step).first()
                    if coupon_config:
                        logger.info(f"Creating coupon config for step {new_step.id}")
                        maximum_amount = None if coupon_config.type == 'percentage' else coupon_config.maximum_amount
                        CouponConfig.objects.create(
                            flow_step=new_step,
                            type=coupon_config.type,
                            amount=coupon_config.amount,
                            expire_in=coupon_config.expire_in,
                            maximum_amount=maximum_amount,
                            free_shipping=coupon_config.free_shipping,
                            exclude_sale_products=coupon_config.exclude_sale_products
                        )
                        
                    if not text_config and not delay_config and not coupon_config:
                        logger.warning(f"No configuration found for step {suggested_step.id}")
                        
                except Exception as step_error:
                    logger.error(f"Error creating config for step {new_step.id}: {str(step_error)}")
                    raise
            
            messages.success(
                request,
                'Suggested flow activated successfully. You can now customize it.'
            )
            return redirect('flow', flow_id=new_flow.id)
            
    except Exception as e:
        logger.error(f"Error activating suggested flow: {str(e)}", exc_info=True)
        messages.error(
            request,
            'An error occurred while activating the suggested flow. Please try again.'
        )
        return redirect('flows')


@login_required(login_url='login')
@check_token_validity
def campaign(request, context=None):
    if context is None:
        context = {}
    try:
        store = UserStoreLink.objects.get(user=request.user).store
        store_groups_response = group_campaign(request.user)
        
        if not store_groups_response.get('success'):
            messages.error(request, 'Failed to fetch store groups.')
            return redirect('dashboard')
        
        store_groups = store_groups_response.get('data', [])

    except UserStoreLink.DoesNotExist:
        messages.error(request, 'No store linked. Please link a store first.')
        return redirect('dashboard')

    if request.method == 'POST':
        form = CampaignForm(request.POST, store_groups=store_groups)
        if form.is_valid():
            msg = form.cleaned_data['msg']
            status = form.cleaned_data['status']
            group_id = form.cleaned_data['customers_group']
            scheduled_time = form.cleaned_data['scheduled_time']

            # Only perform the additional validations if the status is 'active'
            if status == 'scheduled':
                if scheduled_time.tzinfo is None or scheduled_time.tzinfo.utcoffset(scheduled_time) is None:
                    scheduled_time = make_aware(scheduled_time)
                if scheduled_time < make_aware(datetime.now()):
                    messages.error(request, 'Scheduled time cannot be in the past.')
                    return redirect('campaigns')

                # Fetch customers only for active campaigns
                customers_data = get_customers_from_group(request.user, group_id)
                customers_numbers = [customer['customer_number'] for customer in customers_data]

                if len(customers_data) == 0:
                    messages.error(request, 'No customers in the selected group.')
                    return redirect('campaigns')

                # Check if the message limit is sufficient
                if len(customers_numbers) > store.subscription.messages_limit - store.subscription_message_count:
                    messages.error(request, 'Insufficient message balance.')
                    return redirect('campaigns')
            else:
                # Set customers_data and customers_numbers to empty if it's a draft
                customers_data = []
                customers_numbers = []

            # Save the campaign and get the campaign ID
            campaign = form.save(commit=False)
            campaign.status = status
            campaign.store = store
            campaign.scheduled_time = scheduled_time
            campaign.save()
            
            data = {
                'customers_data': customers_data,
                'msg': msg,
                'store_id': store.id,
                'campaign_id': campaign.id
            }

            # Schedule the task only if the status is 'active'
            if status == 'scheduled':
                task = send_whatsapp_message_task.apply_async(args=[data])
                campaign.task_id = task.id
                campaign.save()
                messages.success(request, 'Campaign created and sent successfully.')
            else:
                messages.success(request, 'Campaign saved as draft.')
            
            return redirect('campaigns')  # Adjust the redirect as needed
    else:
        form = CampaignForm(store_groups=store_groups)
    
    context.update({
        'form': form,
    })
    
    return render(request, 'base/campaigns.html', context)
        

@login_required(login_url='login')
def edit_campaign(request, campaign_id):
    try:
        store = UserStoreLink.objects.get(user=request.user).store
        campaign = Campaign.objects.get(id=campaign_id, store=store)
        
        # Only allow editing if the campaign is 'scheduled' or 'failed'
        if campaign.status not in ['scheduled', 'draft']:
            messages.error(request, 'This campaign cannot be updated as it is not scheduled.')
            return redirect('campaigns')
        
        store_groups_response = group_campaign(request.user)
        store_groups = store_groups_response.get('data', [])

        if request.method == 'POST':
            form = CampaignForm(request.POST, instance=campaign, store_groups=store_groups)
            if form.is_valid():
                status = form.cleaned_data['status']
                scheduled_time = form.cleaned_data['scheduled_time']
                group_id = form.cleaned_data['customers_group']
                msg = form.cleaned_data['msg']
                
                # If the campaign is 'scheduled', validate and reschedule
                if status == 'scheduled':
                    # Revoke the old task if there is one
                    if campaign.task_id:
                        celery_app.control.revoke(campaign.task_id, terminate=True)

                    # Ensure scheduled_time is timezone-aware and in the future
                    if scheduled_time.tzinfo is None or scheduled_time.tzinfo.utcoffset(scheduled_time) is None:
                        scheduled_time = make_aware(scheduled_time)
                    if scheduled_time < make_aware(datetime.now()):
                        messages.error(request, 'Scheduled time cannot be in the past.')
                        return redirect('campaigns')
                    
                    # Fetch customers for the selected group
                    customers_data = get_customers_from_group(request.user, group_id)
                    customers_numbers = [customer['customer_number'] for customer in customers_data]

                    if len(customers_numbers) == 0:
                        messages.error(request, 'No customers in the selected group.')
                        return redirect('campaigns')
                    
                    if len(customers_data) == 0:
                        messages.error(request, 'No customers in the selected group.')
                        return redirect('campaigns')

                    # Check if the message limit is sufficient
                    if len(customers_numbers) > store.subscription.messages_limit - store.subscription_message_count:
                        messages.error(request, 'Insufficient message balance.')
                        return redirect('campaigns')
                    
                    data = {
                        'customers_data': customers_data,
                        'msg': msg,
                        'store_id': store.id,
                        'campaign_id': campaign.id
                    }

                    # Schedule the task with the new time
                    task = send_whatsapp_message_task.apply_async(eta=scheduled_time, args=[data])
                    
                    # Update the campaign's task_id and status to 'scheduled'
                    campaign.task_id = task.id
                    campaign.status = 'scheduled'
                    campaign.scheduled_time = scheduled_time
                    campaign.save(update_fields=['task_id', 'status', 'scheduled_time'])
                    messages.success(request, 'Campaign updated and rescheduled successfully.')
                
                # If status is 'draft' or any other, just save without scheduling
                else:
                    campaign.status = status
                    campaign.scheduled_time = scheduled_time
                    campaign.save(update_fields=['status', 'scheduled_time'])
                    messages.success(request, 'Campaign updated successfully as a draft.')

                return redirect('campaigns')
            else:
                messages.error(request, 'Form is invalid.')
                return redirect('campaigns')

    except Campaign.DoesNotExist:
        messages.error(request, 'Campaign not found.')
        return redirect('campaigns')
    except UserStoreLink.DoesNotExist:
        messages.error(request, 'No store linked. Please link a store first.')
        return redirect('dashboard')
    
    # Render form with initial data
    form = CampaignForm(instance=campaign, store_groups=store_groups)
    context = {
        'form': form,
        'campaign': campaign,
    }
    return render(request, 'base/edit_campaign.html', context)





@login_required
def get_campaign_data(request, campaign_id=None):
    try:
        # Fetch a specific campaign by ID
        store = UserStoreLink.objects.get(user=request.user).store
        if campaign_id:
            campaign = Campaign.objects.get(id=campaign_id, store=UserStoreLink.objects.get(user=request.user).store)
            data = {
                'name': campaign.name,
                'scheduled_time': campaign.scheduled_time.strftime('%Y-%m-%d %H:%M'),  # Adjust format as per input type
                'customers_group': campaign.customers_group,
                'status': campaign.status,
                'status_display': dict(Campaign.status_choices).get(campaign.status, campaign.status),
                'msg': campaign.msg,
                'edit_url': reverse('edit_campaign', args=[campaign.id]),  # Add edit URL
                'delete_url': reverse('campaign_delete', args=[campaign.id])  # Add delete URL
            }
            

                
            return JsonResponse({'success': True, 'data': data})
        else:
            # Fetch all campaigns
            campaigns = Campaign.objects.filter(store=store, status__in=['scheduled', 'failed', 'sent', 'draft','cancelled']).order_by('-scheduled_time')
            data = [{
                'id': campaign.id,
                'name': campaign.name,
                'scheduled_time': campaign.scheduled_time.strftime('%Y-%m-%d %H:%M'),  # Adjust format as per input type
                'messages_sent': campaign.messages_sent,
                'status': campaign.status,
                'status_display': dict(Campaign.status_choices).get(campaign.status, campaign.status),
                'edit_url': reverse('edit_campaign', args=[campaign.id]),  # Add edit URL for each campaign
                'delete_url': reverse('campaign_delete', args=[campaign.id]),  # Add delete URL for each campaign
                'cancel_url': reverse('campaign_cancel', args=[campaign.id])
            } for campaign in campaigns
                    ]
            
            
            return JsonResponse({'success': True, 'data': data}, status=200)
    except Campaign.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Campaign not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

    
@login_required(login_url='login')
def campaign_cancel(request, campaign_id):
    try:
        # Get the store linked to the logged-in user
        user_store = UserStoreLink.objects.get(user=request.user).store
        # Fetch the campaign belonging to the user's store
        campaign = Campaign.objects.get(id=campaign_id, store=user_store)

        # Check if the campaign is scheduled
        if campaign.status != 'scheduled':
            messages.error(request, 'This campaign is not scheduled, so it cannot be cancelled.')
            return redirect('campaigns')

        # Check if the campaign has a task ID (Celery task)
        if campaign.task_id:
            try:
                # Try to revoke the task using Celery
                celery_app.control.revoke(campaign.task_id)
            except CeleryError as e:
                # Log the error and display a user-friendly message
                messages.error(request, f"Failed to revoke the campaign task: {str(e)}")
            else:
                # If successfully revoked, update campaign status
                campaign.task_id = None
                campaign.status = 'cancelled'
                campaign.save(update_fields=['task_id', 'status'])
                messages.success(request, 'Campaign has been successfully cancelled.')
                
        else:
            campaign.status = 'cancelled'
            campaign.save(update_fields=['task_id', 'status'])
            messages.success(request, 'No task ID found for this campaign. Cancelling the campaign.')
            
    except (Campaign.DoesNotExist, UserStoreLink.DoesNotExist):
        # If either the campaign or the user-store link does not exist
        raise PermissionDenied('You do not have permission to cancel this campaign.')

    # Redirect to the campaigns page
    return redirect('campaigns')


@login_required(login_url='login')
def delete_campaign(request, campaign_id):
    try:
        campaign = Campaign.objects.get(id=campaign_id , store=UserStoreLink.objects.get(user=request.user).store)
        campaign.status = 'deleted'
        campaign.save(update_fields=['status'])
        messages.success(request, 'Campaign deleted successfully.')
    except Campaign.DoesNotExist:
        messages.error(request, 'Campaign does not exist.')
    return redirect('campaigns')


#Customer Views
@login_required(login_url='login')
@check_token_validity
def customers_view(request, context=None):
    try:
        store = UserStoreLink.objects.get(user=request.user).store
        
    except UserStoreLink.DoesNotExist:
        messages.error(request, 'No store linked. Please link a store first.')
        return redirect('dashboard')
    
    if context is None:
        context = {}
    
    form = GroupCreationForm()
    if request.method == 'POST':
        form = GroupCreationForm(request.POST)
        
        if form.is_valid():
            group_name = form.cleaned_data['name']
            conditions = form.cleaned_data['conditions']
            response = create_customer_group(request.user, group_name, conditions)
            if response.get('success') == True:
                messages.success(request, 'Group created successfully.')
                return redirect('customers')
            else:
                #get the field name and the error message
                error_message = response.get('error', {}).get('message', 'An error occurred')
                error_fields = response.get('error', {}).get('fields', {})
                for field, messages_list in error_fields.items():
                    for field_error in messages_list:
                        messages.error(request, f"{error_message} - {field}: {field_error}")
                return redirect('customers')
        else:
            messages.error(request, 'Error creating group. Please correct the form errors 2.')
            return redirect('customers')
    
    context.update({
        'form': form,
    })
    
    return render(request, 'base/customer_list.html',context)


from django.db.models import Count
from django.http import JsonResponse

@login_required(login_url='login')
def get_customers(request):
    try:
        # Get the store associated with the logged-in user
        store = UserStoreLink.objects.get(user=request.user).store

        # Retrieve customers for the specific store
        customers_list = Customer.objects.filter(store=store)

        # Prepare customer data
        customers_data = [{
            'name': customer.customer_name,
            'email': customer.customer_email,
            'phone': customer.customer_phone,
            'location': customer.customer_location,
            'groups': list(customer.customer_groups.values_list('name', flat=True)),  # Group IDs
            'updated_at': customer.customer_updated_at,
        } for customer in customers_list]

        # Calculate group counts

        # Create a dictionary of group IDs to names
        group_data = (
            Group.objects.filter(store=store)
            .annotate(customer_count=Count('customers'))  # Count related customers for each group
            .values('name', customer_count=Count('customers'))  # Include group name and customer count
        )

        # Convert to list of dictionaries for easier JSON handling
        group_data_list = list(group_data)
        

        return JsonResponse({
            'customers': customers_data,
            'group_data': group_data_list,  # List of dictionaries with 'name' and 'customer_count'
            'total_count': len(customers_list),
        }, status=200)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)



@login_required(login_url='login')
@transaction.atomic
def sync_data(request):
    try:
        # Fetch the latest customer data from the API
        customer_data = get_customer_data(request.user)
        if not customer_data.get('success', False):
            logger.error("Failed to fetch customer data from API.")
            return JsonResponse({'error': 'فشل في جلب بيانات العملاء من واجهة برمجة التطبيقات'}, status=500)

        # Get the store associated with the logged-in user
        store = Store.objects.get(userstorelink__user=request.user)

        # Clear out existing customers for this store but keep groups intact
        Customer.objects.filter(store=store).delete()

        # Update or create groups based on the data received
        group_id_to_name = customer_data.get('group_id_to_name', {})
        print(group_id_to_name)
        for group_id, group_name in group_id_to_name.items():
            Group.objects.get_or_create(
                group_id=group_id,
                store=store,
                defaults={'name': group_name}  # Corrected to ensure it's a dictionary
            )

        # Add new customers and associate them with groups
        customers_list = customer_data['customers']
        for customer in customers_list:
    # Create the customer entry
            customer_obj = Customer.objects.create(
                store=store,
                customer_name=customer['name'],
                customer_email=customer['email'],
                customer_phone=customer['phone'],
                customer_location=customer['location'],
                customer_updated_at=customer['updated_at'],
            )

            # Debug print: check group IDs for the customer
            group_ids = customer.get('groups', [])
            print(f"Customer: {customer['name']}, Group IDs: {group_ids}")

            # Associate the customer with groups
            groups = Group.objects.filter(group_id__in=group_ids, store=store)
            print(f"Associating {customer['name']} with Groups: {[g.group_id for g in groups]}")  # Debug print for groups found
            customer_obj.customer_groups.set(groups)

        return JsonResponse({'status': 'success', 'message': 'تم تحديث قاعدة البيانات بنجاح.'}, status=200)

    except Exception as e:
        logger.error("Error during sync: %s", e, exc_info=True)
        return JsonResponse({'error': 'حدث خطأ أثناء المزامنة.'}, status=500)

    
    
@login_required(login_url='login')
def delete_customer_list(request, group_id):
    response = delete_customer_group(request.user, group_id)
    if response.get('success'):
        messages.success(request, 'Group deleted successfully.')
        return redirect('customers')
    else:
        messages.error(request, 'Error deleting group.')
        return redirect('customers')

