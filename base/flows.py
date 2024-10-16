from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.core.exceptions import ValidationError
from django.db import transaction
from .models import Flow, FlowStep, FlowActionTypes, TextConfig, TimeDelayConfig, Trigger
from .forms import FlowForm
import json
import logging


logger = logging.getLogger(__name__)

class FlowBuilderError(Exception):
    """Custom exception for Flow Builder specific errors"""
    pass


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
    
def validate_flow_for_activation(flow):
    """
    Validate if a flow meets requirements for activation.
    Returns (bool, str) tuple - (is_valid, error_message)
    """
    # Get all steps for the flow ordered by their sequence
    steps = FlowStep.objects.filter(flow=flow).order_by('order')
    
    if not steps.exists():
        return False, "Flow must have at least one step to be activated"
    
    # Validate each step has proper configuration
    for step in steps:
        if step.action_type.name == 'sms':
            if not hasattr(step, 'text_config') or not step.text_config.message.strip():
                return False, f"Step {step.order} (SMS) is missing message content"
        elif step.action_type.name == 'delay':
            if not hasattr(step, 'time_delay_config'):
                return False, f"Step {step.order} (Delay) is missing delay configuration"
    
    return True, ""

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
            # Process the steps first
            process_flow_steps(flow, steps_data)
            
            # After all steps are processed, attempt to activate the flow
            is_valid, error_message = validate_flow_for_activation(flow)
            
            if is_valid:
                # Update the flow status to active
                flow.status = 'active'
                flow.save()
                logger.info(f"Flow {flow.id} has been activated successfully")
                activation_message = "Flow has been activated successfully"
            else:
                # Keep the flow in draft status
                flow.status = 'draft'
                flow.save()
                logger.warning(f"Flow {flow.id} could not be activated: {error_message}")
                activation_message = f"Flow saved as draft: {error_message}"

        # If we get here, everything worked, so we can commit
        transaction.savepoint_commit(sid)
        
        # Log success
        logger.info(f"Successfully updated flow {flow.id} with {len(steps_data)} steps")
        
        return JsonResponse({
            'success': True,
            'redirect_url': request.build_absolute_uri(),
            'message': 'Flow updated successfully',
            'activation_status': {
                'is_active': flow.status == 'active',
                'message': activation_message
            }
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