from django.shortcuts import render,redirect
import random
import string
from django.contrib.auth import authenticate
from celery.exceptions import CeleryError
from django.core.exceptions import PermissionDenied
from django.contrib import messages
from django.db import transaction
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.utils.timezone import make_aware
from . forms import CreateUserForm, UserEventForm, CampaignForm, GroupCreationForm, FlowForm
from . models import User, Store, UserStoreLink, UserEvent, EventType,Trigger, Campaign, FlowActionTypes, Flow, FlowStep, SuggestedFlow, SuggestedFlowStep, TextConfig, TimeDelayConfig,SuggestedTextConfig, SuggestedTimeDelayConfig
from django.http import JsonResponse
from automations.tasks import send_email_task
from . apis import get_customer_data, create_customer_group, delete_customer_group,group_campaign, get_customers_from_group
from django.utils.crypto import get_random_string
from Risalabot.celery import app as celery_app
from datetime import datetime
from django.db.models import F
from django.db import models
from django.shortcuts import get_object_or_404
import json
from django.core.exceptions import ValidationError
from django.urls import reverse
import logging



__all__ = ('celery_app',) 

logger = logging.getLogger(__name__)

class FlowBuilderError(Exception):
    """Custom exception for Flow Builder specific errors"""
    pass


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
def dashboard(request):
    user_linked = UserStoreLink.objects.filter(user=request.user).exists()
    store = None
    message_count = 0
    if user_linked:
        store_link = UserStoreLink.objects.get(user=request.user)
        store = store_link.store
        message_count = store.message_count


    context = {
        'user_linked': user_linked,
        'store': store,
        'message_count': message_count
    }

    return render(request, 'base/dashboard.html', context)

@login_required(login_url='login')
def manage_event(request, event_id=None):
    try:
        store = UserStoreLink.objects.get(user=request.user).store
        events = UserEvent.objects.filter(store=store)
    except UserStoreLink.DoesNotExist:
        messages.error(request, 'No store linked. Please link a store first.')
        return redirect('dashboard')
    
    event = None
    if event_id:
        event = UserEvent.objects.get(id=event_id, store=UserStoreLink.objects.get(user=request.user).store)

    if request.method == 'POST':
        form = UserEventForm(request.POST, instance=event)
        if form.is_valid():
            event_type = form.cleaned_data['event_type']
            subcategory = form.cleaned_data['subcategory']
            
            if UserEvent.objects.filter(store=store, event_type=event_type, subcategory=subcategory).exclude(id=event_id).exists():
                messages.error(request, 'You have already created an event for this type and subcategory.')
            else:
                event = form.save(commit=False)
                event.store = store
                event.save()
                if event_id:
                    messages.success(request, 'Event updated successfully.')
                else:
                    messages.success(request, 'Event created successfully.')
            return redirect('events')
        else:
            messages.error(request, 'Error saving event. Please correct the form errors.')
    else:
        form = UserEventForm(instance=event)

    try:
        order_updated_event_type = EventType.objects.get(name='order.updated')
        order_updated_event_type_id = order_updated_event_type.id
    except EventType.DoesNotExist:
        order_updated_event_type_id = None

    context = {
        'events': events,
        'form': form,
        'event': event,
        'order_updated_event_type_id': order_updated_event_type_id,
    }
    return render(request, 'base/events.html', context)

@login_required(login_url='login')
def delete_event(request, event_id):
    event = UserEvent.objects.get(id=event_id, store=UserStoreLink.objects.get(user=request.user).store)
    event.delete()
    messages.success(request, 'Event deleted successfully.')
    return redirect('events')


@login_required(login_url='login')
def flows(request):
    try:
        user = request.user
        flows = user.flows.all()
    except UserStoreLink.DoesNotExist:
        messages.error(request, 'No store linked. Please link a store first.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = FlowForm(request.POST)
        if form.is_valid():
            # Save the form but don't commit yet, as we need to add the owner
            new_flow = form.save(commit=False)
            new_flow.owner = request.user  # Associate the flow with the current user
            new_flow.save()  # Now save the flow
            return redirect('flow', flow_id=new_flow.id)  # Redirect to the flow builder
    else:
        form = FlowForm()
    
    context = {
        'flows': flows,
        'suggestions': SuggestedFlow.objects.all(),
        'form': form
    }
    return render(request, 'base/flows.html', context)

    


@login_required(login_url='login')
def flow_builder(request, flow_id):
    """
    Handle flow building operations with comprehensive error handling and data validation.
    """
    try:
        flow = Flow.objects.get(id=flow_id, owner=request.user)
    except Flow.DoesNotExist:
        logger.warning(f"Flow {flow_id} not found for user {request.user.id}")
        messages.error(request, 'Flow not found.')
        return redirect('flows')

    if request.method == 'POST':
        return handle_flow_update(request, flow)

    # GET request handling
    try:
        flow_steps = FlowStep.objects.filter(flow=flow).order_by('order')
        action_types = FlowActionTypes.objects.all()

        return render(request, 'base/flow_builder.html', {
            'flow': flow,
            'triggers': Trigger.objects.all(),
            'form': FlowForm(instance=flow),
            'flow_steps': flow_steps,
            'action_types': action_types,
        })
    except Exception as e:
        logger.error(f"Error loading flow builder page: {str(e)}", exc_info=True)
        messages.error(request, 'An error occurred while loading the flow builder.')
        return redirect('flows')

def handle_flow_update(request, flow):
    """
    Handle the POST request for updating a flow and its steps.
    """
    # Create a savepoint for potential rollback
    sid = transaction.savepoint()
    
    try:
        # Validate and save flow form
        form = FlowForm(request.POST, instance=flow)
        if not form.is_valid():
            raise ValidationError(form.errors)

        # Parse and validate steps data
        steps_data = request.POST.get('steps')
        if not steps_data:
            raise FlowBuilderError("No steps data provided")

        try:
            steps_data = json.loads(steps_data)
        except json.JSONDecodeError:
            raise FlowBuilderError("Invalid steps data format")

        # Validate steps data structure
        validate_steps_data(steps_data)

        # Start the update process
        with transaction.atomic():
            # Save the flow first
            flow = form.save()
            
            # Store original state for rollback if needed
            original_steps = list(FlowStep.objects.filter(flow=flow).select_related(
                'text_config', 
                'time_delay_config'
            ))

            # Process the steps
            process_flow_steps(flow, steps_data)

        # If we get here, everything worked, so we can commit
        transaction.savepoint_commit(sid)
        
        # Log success
        logger.info(f"Successfully updated flow {flow.id} with {len(steps_data)} steps")
        
        return JsonResponse({
            'success': True,
            'redirect_url': request.build_absolute_uri(),
            'message': 'Flow updated successfully'
        })

    except ValidationError as e:
        transaction.savepoint_rollback(sid)
        logger.error(f"Validation error in flow {flow.id}: {str(e)}")
        return JsonResponse({
            'success': False,
            'errors': {
                'form': form.errors if 'form' in locals() else {},
                'validation': str(e)
            }
        })
    except FlowBuilderError as e:
        transaction.savepoint_rollback(sid)
        logger.error(f"Flow builder error in flow {flow.id}: {str(e)}")
        return JsonResponse({
            'success': False,
            'errors': {'flow_builder': str(e)}
        })
    except Exception as e:
        transaction.savepoint_rollback(sid)
        logger.error(f"Unexpected error in flow {flow.id}: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'errors': {'server': 'An unexpected error occurred. Please try again.'}
        })

def validate_steps_data(steps_data):
    """
    Validate the structure and content of steps data.
    """
    if not isinstance(steps_data, list):
        raise FlowBuilderError("Steps data must be a list")

    for index, step in enumerate(steps_data):
        if not isinstance(step, dict):
            raise FlowBuilderError(f"Step {index} must be an object")

        required_fields = ['action_type', 'content']
        for field in required_fields:
            if field not in step:
                raise FlowBuilderError(f"Step {index} is missing required field: {field}")

        if not isinstance(step['content'], dict):
            raise FlowBuilderError(f"Step {index} content must be an object")

        # Validate specific action types
        action_type = step['action_type']
        content = step['content']

        if action_type == 'sms':
            if 'message' not in content or not content['message'].strip():
                raise FlowBuilderError(f"Step {index}: SMS message cannot be empty")
        elif action_type == 'delay':
            if 'delay_time' not in content:
                raise FlowBuilderError(f"Step {index}: Delay time is required")
            try:
                delay_time = int(content['delay_time'])
                if delay_time < 1:
                    raise FlowBuilderError(f"Step {index}: Delay time must be positive")
            except ValueError:
                raise FlowBuilderError(f"Step {index}: Invalid delay time format")

def process_flow_steps(flow, steps_data):
    """
    Process and save flow steps with their configurations.
    """
    existing_steps_ids = []

    for index, step_data in enumerate(steps_data, start=1):
        step = handle_step_creation_or_update(flow, step_data, index)
        if step:
            existing_steps_ids.append(step.id)

    # Safely delete steps that are no longer in the flow
    removed_steps = FlowStep.objects.filter(flow=flow).exclude(id__in=existing_steps_ids)
    for step in removed_steps:
        try:
            step.delete()
            logger.info(f"Deleted step {step.id} from flow {flow.id}")
        except Exception as e:
            logger.error(f"Error deleting step {step.id}: {str(e)}")
            raise

def handle_step_creation_or_update(flow, step_data, index):
    """
    Handle the creation or update of a single flow step and its configuration.
    """
    try:
        step_id = step_data.get('step_id')
        action_type = step_data['action_type']
        content = step_data.get('content', {})

        # Get or create the step
        if step_id:
            step = FlowStep.objects.get(id=step_id, flow=flow)
            action_type_obj = FlowActionTypes.objects.get(name=action_type)
            
            # If action type changed, handle cleanup
            if step.action_type != action_type_obj:
                handle_action_type_change(step, action_type_obj)
            
            step.order = index
            step.action_type = action_type_obj
            step.save()
        else:
            action_type_obj = FlowActionTypes.objects.get(name=action_type)
            step = FlowStep.objects.create(
                flow=flow,
                order=index,
                action_type=action_type_obj
            )

        # Handle step configuration
        handle_step_configuration(step, action_type, content)

        return step

    except FlowStep.DoesNotExist:
        logger.warning(f"Step {step_id} not found in flow {flow.id}")
        return None
    except FlowActionTypes.DoesNotExist:
        logger.error(f"Invalid action type: {action_type}")
        raise FlowBuilderError(f"Invalid action type: {action_type}")
    except Exception as e:
        logger.error(f"Error processing step in flow {flow.id}: {str(e)}")
        raise

def handle_action_type_change(step, new_action_type):
    """
    Handle cleanup when a step's action type changes.
    """
    TextConfig.objects.filter(flow_step=step).delete()
    TimeDelayConfig.objects.filter(flow_step=step).delete()
    step.action_type = new_action_type

def handle_step_configuration(step, action_type, content):
    """
    Handle the configuration for a specific step based on its action type.
    """
    try:
        if action_type == 'sms':
            TimeDelayConfig.objects.filter(flow_step=step).delete()
            TextConfig.objects.update_or_create(
                flow_step=step,
                defaults={'message': content.get('message', '').strip()}
            )

        elif action_type == 'delay':
            TextConfig.objects.filter(flow_step=step).delete()
            TimeDelayConfig.objects.update_or_create(
                flow_step=step,
                defaults={
                    'delay_time': int(content.get('delay_time', 1)),
                    'delay_type': content.get('delay_type', 'hours')
                }
            )
    except Exception as e:
        logger.error(f"Error handling configuration for step {step.id}: {str(e)}")
        raise FlowBuilderError(f"Error configuring step: {str(e)}")

@login_required(login_url='login')
def delete_flow(request, event_id):
    flow = Flow.objects.get(id=event_id, owner=request.user)
    flow.delete()
    messages.success(request, 'Flow deleted successfully.')
    return redirect('flows')

@login_required
def activate_suggested_flow(request, suggestion_id):
    # Get the suggested flow to copy
    suggested_flow = get_object_or_404(SuggestedFlow, id=suggestion_id)

    # Create a new Flow for the current user
    new_flow = Flow.objects.create(
        owner=request.user,
        name=suggested_flow.name,
        trigger=suggested_flow.trigger  # Copy trigger from the suggested flow
    )

    # Copy the steps from the suggested flow to the new flow
    for suggested_step in suggested_flow.steps.all():
        FlowStep.objects.create(
            flow=new_flow,
            order=suggested_step.order,
            action_type=suggested_step.action_type,
        )

    # Copy text configs from the suggested flow to the new flow
    for suggested_text_config in SuggestedTextConfig.objects.filter(id=suggested_flow.id):
        TextConfig.objects.create(
            flow=new_flow,
            order=suggested_text_config.order,
            text=suggested_text_config.text
        )

    # Copy time delay configs from the suggested flow to the new flow
    for suggested_time_delay_config in SuggestedTimeDelayConfig.objects.filter(id=suggested_flow.id):
        TimeDelayConfig.objects.create(
            flow=new_flow,
            order=suggested_time_delay_config.order,
            delay=suggested_time_delay_config.delay
        )

    # After copying, redirect to the flow builder to allow further customization
    return redirect('flow', flow_id=new_flow.id)



@login_required(login_url='login')
def campaign(request):
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
            group_id = form.cleaned_data['customers_group']
            scheduled_time = form.cleaned_data['scheduled_time']
            if scheduled_time.tzinfo is None or scheduled_time.tzinfo.utcoffset(scheduled_time) is None:
                scheduled_time = make_aware(scheduled_time)
            if scheduled_time < make_aware(datetime.now()):
                messages.error(request, 'Scheduled time cannot be in the past.')
                return redirect('campaigns')

            customers_numbers = get_customers_from_group(request.user, group_id)

            if len(customers_numbers) == 0:
                messages.error(request, 'No customers in the selected group.')
                return redirect('campaigns')

            if len(customers_numbers) > store.subscription.messages_limit - store.message_count:
                messages.error(request, 'Insufficient message balance.')
                return redirect('campaigns')

            # Save the campaign and get the campaign ID
            campaign = form.save(commit=False)
            campaign.status = 'scheduled'
            campaign.store = store
            campaign.save()

            # Pass the campaign_id to the task
            task = send_email_task.apply_async(eta=scheduled_time, args=[customers_numbers, msg, store.id, campaign.id])
            print(customers_numbers)
            campaign.task_id = task.id
            campaign.save()
            
            
            return redirect('campaigns')  # Adjust the redirect as needed
    else:
        form = CampaignForm(store_groups=store_groups)
    
    context = {
        'form': form,
    }
    
    return render(request, 'base/campaigns.html', context)

        
def edit_campaign(request, campaign_id):
    try:
        store = UserStoreLink.objects.get(user=request.user).store
        campaign = Campaign.objects.get(id=campaign_id, store=store)
        
        if campaign.status != 'scheduled':
            messages.error(request, 'This campaign is not scheduled, so it cannot be updated.')
            return redirect('campaigns')
        
        if request.method == 'POST':
            store_groups_response = group_campaign(request.user)
            store_groups = store_groups_response.get('data', [])

            form = CampaignForm(request.POST, instance=campaign, store_groups=store_groups)
            if form.is_valid():

                # Revoke the old task
                if campaign.task_id:
                    celery_app.control.revoke(campaign.task_id, terminate=True)

                # Update campaign details
                form.save()

                # Schedule the new task with updated data
                msg = form.cleaned_data['msg']
                group_id = form.cleaned_data['customers_group']
                scheduled_time = form.cleaned_data['scheduled_time']
                #check if the scheduled time is timezone aware and not in the past
                if scheduled_time.tzinfo is None or scheduled_time.tzinfo.utcoffset(scheduled_time) is None:
                    scheduled_time = make_aware(scheduled_time)
                if scheduled_time < make_aware(datetime.now()):
                    messages.error(request, 'Scheduled time cannot be in the past.')
                    return redirect('campaigns')
                                    
                
                
                customers_numbers = get_customers_from_group(request.user, group_id)

                if len(customers_numbers) == 0:
                    messages.error(request, 'No customers in the selected group.')
                    return redirect('campaigns')

                # Schedule the new task
                task = send_email_task.apply_async(eta=scheduled_time, args=[customers_numbers, msg, store.id, campaign.id])
                
                # Save the new task_id
                campaign.task_id = task.id
                campaign.status = 'scheduled'
                campaign.save(update_fields=['task_id', 'status'])

                messages.success(request, 'Campaign updated and rescheduled successfully.')
                return redirect('campaigns')
            else:
                # Handle form errors
                messages.error(request, 'Form is invalid.')
                return redirect('campaigns')

    except Campaign.DoesNotExist:
        messages.error(request, 'Campaign not found.')
        return redirect('campaigns')




@login_required
def get_campaign_data(request, campaign_id=None):
    try:
        # Fetch a specific campaign by ID
        store = UserStoreLink.objects.get(user=request.user).store
        if campaign_id:
            campaign = Campaign.objects.get(id=campaign_id, store=UserStoreLink.objects.get(user=request.user).store)
            data = {
                'name': campaign.name,
                'scheduled_time': campaign.scheduled_time.strftime('%Y-%m-%dT%H:%M'),  # Adjust format as per input type
                'customers_group': campaign.customers_group,
                'status': campaign.status,
                'msg': campaign.msg,
                'edit_url': reverse('edit_campaign', args=[campaign.id]),  # Add edit URL
                'delete_url': reverse('campaign_delete', args=[campaign.id])  # Add delete URL
            }
            return JsonResponse({'success': True, 'data': data})
        else:
            # Fetch all campaigns
            campaigns = Campaign.objects.filter(store=store, status__in=['scheduled', 'failed', 'completed', 'draft','cancelled']).order_by('-scheduled_time')
            data = [{
                'id': campaign.id,
                'name': campaign.name,
                'scheduled_time': campaign.scheduled_time.strftime('%Y-%m-%d %H:%M'),  # Adjust format as per input type
                'store': campaign.store.store_name,
                'status': campaign.status,
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
def customers_view(request):
    try:
        store = UserStoreLink.objects.get(user=request.user).store
        
    except UserStoreLink.DoesNotExist:
        messages.error(request, 'No store linked. Please link a store first.')
        return redirect('dashboard')
    
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
                messages.error(request, 'Error creating group. Please correct the form errors 1.')
                return redirect('customers')
        else:
            messages.error(request, 'Error creating group. Please correct the form errors 2.')
            return redirect('customers')
    
    context = {
        'form': form,
    }
    
    return render(request, 'base/customer_list.html',context)


@login_required(login_url='login')
def get_customers(request):
    try:
        customer_data = get_customer_data(request.user)
        
        if not customer_data['success']:
            return JsonResponse({'error': 'Failed to fetch customer data from API'}, status=500)

        customers_list = customer_data['customers']

        customers_data = [{
            'name': customer['name'],
            'email': customer['email'],
            'phone': customer['phone'],
            'location': customer['location'],
            'groups': customer['groups'],
            'updated_at': customer['updated_at'],
        } for customer in customers_list]

        return JsonResponse({
            'customers': customers_data,
            'group_counts': customer_data.get('group_counts', {}),
            'group_id_to_name': customer_data.get('group_id_to_name', {}),
            'total_count': len(customers_list),
        }, status=200)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

    
    
@login_required(login_url='login')
def delete_customer_list(request, group_id):
    response = delete_customer_group(request.user, group_id)
    if response.get('success'):
        messages.success(request, 'Group deleted successfully.')
        return redirect('customers')
    else:
        messages.error(request, 'Error deleting group.')
        return redirect('customers')
