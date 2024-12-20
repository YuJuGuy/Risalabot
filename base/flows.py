import logging
from django.db import IntegrityError
from django.core.exceptions import ValidationError
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.urls import reverse
from . decorators import check_token_validity
from . models import User, UserStoreLink,Trigger, FlowActionTypes, Flow, FlowStep, SuggestedFlow, SuggestedFlowStep, TextConfig, TimeDelayConfig,SuggestedTextConfig, SuggestedTimeDelayConfig, CouponConfig, SuggestedCouponConfig, Notification
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
import json
from django.db import transaction
from django.shortcuts import render
from django.db.models import F
from . forms import FlowForm
from django.core.exceptions import PermissionDenied
import sys
from django.shortcuts import redirect

logger = logging.getLogger(__name__)

stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setLevel(logging.INFO)
stream_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
stream_handler.stream.reconfigure(encoding='utf-8')  # Set encoding to UTF-8

# Add the handler to the logger
logger.addHandler(stream_handler)


__all__ = ('celery_app',) 



@login_required(login_url='login')
@check_token_validity
def flows(request, context=None):
    # Ensure context is never overwritten, but rather updated
    if context is None:
        context = {}

    try:
        # Assuming this is now guaranteed to be valid from the decorator
        user_store_link = UserStoreLink.objects.get(user=request.user)
        store = user_store_link.store
        context['notification_count'] = Notification.objects.filter(store=store).count()
        context['notifications'] = Notification.objects.filter(store=store).order_by('-created_at')
    except UserStoreLink.DoesNotExist:
        return redirect('dashboard')

    if request.method == 'POST':
        form = FlowForm(request.POST)
        if not store.subscription:
            return JsonResponse({'success': False, 'type': 'error', 'message': 'المتجر غير مشترك بالخدمة.'}, status=400)

        if form.is_valid():
            # Save the form but don't commit yet, as we need to add the owner
            new_flow = form.save(commit=False)
            new_flow.owner = request.user  # Associate the flow with the current user
            new_flow.store = store
            new_flow.save()  # Now save the flow
            return JsonResponse({'success': True, 'redirect_url': reverse('flow', kwargs={'flow_id': new_flow.id})})
        else:
            error_messages = form.get_custom_errors()
            return JsonResponse({'success': False, 'type': 'error', 'message': error_messages}, status=400)

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
        flows = list(user.flows.all().values('id', 'name', 'updated_at', 'status', 'messages_sent','purchases').exclude(status='deleted'))
        for flow in flows:
            flow['status'] = dict(Flow.STATUS_CHOICES).get(flow['status'], flow['status'])
        for flow in flows:
            flow['updated_at'] = flow['updated_at'].strftime('%Y-%m-%d %H:%M')
        suggestions = list(SuggestedFlow.objects.all().values('id', 'name', 'description', 'img'))
        data = {
            'flows': flows,
            'suggestions': suggestions
        }
        return JsonResponse({'success': True, 'data': data})
        
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'type': 'error', 'message': 'لم يتم العثور على المستخدم.'}, status=404)
    

    
def validate_steps_data(steps_data):
        """Validates the steps data sent as JSON."""
        try:
            steps = json.loads(steps_data)
        except json.JSONDecodeError:
            raise ValidationError("بيانات الخطوات يجب أن تكون بتنسيق JSON صالح.")

        # Check if the steps_data is a list
        if not isinstance(steps, list):
            raise ValidationError("بيانات الخطوات يجب أن تكون قائمة.")

        valid_action_types = FlowActionTypes.objects.values_list('name', flat=True)
        
        # Validate each step's structure and content
        for step in steps:
            if 'action_type' not in step or step['action_type'] not in valid_action_types:
                raise ValidationError(f"نوع الاجراء غير صالح: {step.get('action_type')}")

            # SMS action validation
            if step['action_type'] == 'sms':
                message = step.get('content', {}).get('message', '').strip()
                if not message:
                    raise ValidationError("اجراء الرسالة يتطلب رسالة.")

            # Delay action validation
            elif step['action_type'] == 'delay':
                delay_time = step.get('content', {}).get('delay_time')
                delay_type = step.get('content', {}).get('delay_type')

                if not delay_time or not str(delay_time).isdigit():
                    raise ValidationError("اجراء التأخير يتطلب مدة تأخير صالحة.")

                if delay_type not in ['hours', 'days', 'minutes']:
                    raise ValidationError("اختيار نوع التأخير غير صالح. يجب أن يكون 'ساعات' أو 'أيام'.")
                
                
            # Coupon action validation
            elif step['action_type'] == 'coupon':
                coupon_type = step.get('content', {}).get('type')
                amount = step.get('content', {}).get('amount')
                expire_in = step.get('content', {}).get('expire_in')
                maximum_amount = step.get('content', {}).get('maximum_amount')
                free_shipping = step.get('content', {}).get('free_shipping')
                exclude_sale_products = step.get('content', {}).get('exclude_sale_products')
                message = step.get('content', {}).get('message')

                if coupon_type not in ['fixed', 'percentage']:
                    raise ValidationError("اختيار نوع الكوبون غير صالح. يجب أن يكون 'مبلغ ثابت' أو 'نسبة مئوية'.")

                if amount is None or not str(amount).isdigit() or int(amount) <= 0:
                    raise ValidationError("اجراء الكوبون يتطلب مبلغ صالح.")

                if expire_in is None or not str(expire_in).isdigit() or int(expire_in) <= 0:
                    raise ValidationError("اجراء الكوبون يتطلب مدة انتهاء صلاحية صالحة.")

                if maximum_amount is not None and (maximum_amount != "" and (not str(maximum_amount).isdigit() or int(maximum_amount) < 1)):
                    raise ValidationError("لا يمكن أن يكون المبلغ الأقصى أقل من 1.")
                
                if coupon_type == "percentage" and (amount is None or int(amount) > 100):
                    raise ValidationError("لا يمكن أن يكون المبلغ الأقصى أكبر من %100.")

                if free_shipping not in ['True', 'False']:
                    raise ValidationError("يجب أن تكون الشحن مجانية إما نعم أو لا.")
                
                if exclude_sale_products not in ['True', 'False']:
                    raise ValidationError("استبعاد المنتجات المخفضة يجب أن تكون قيمة نعم أو لا.")
                
                if message is None or "{الكوبون}" not in message:
                    raise ValidationError("اجراء الكوبون يتطلب رسالة تحتوي على الكوبون.")
        
        return steps
    
@login_required(login_url='login')
@require_http_methods(["GET", "POST"])
@check_token_validity
def flow_builder(request, flow_id, context=None):

    try:
        user = request.user
        store = UserStoreLink.objects.get(user=request.user).store
        flow = Flow.objects.get(id=flow_id, owner=request.user)
    except UserStoreLink.DoesNotExist:
        logger.error(f"No store linked to your account")
        return JsonResponse({'success': False, 'type': 'error', 'message': 'لم يتم العثور على المستخدم.'}, status=404)
    except Flow.DoesNotExist:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'type': 'error', 'message': 'لم يتم العثور على الأتمتة.'}, status=404)

            
    if context is None:
        context = {}

    if request.method == 'POST':
        store = UserStoreLink.objects.get(user=request.user).store
        if not store.subscription:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'type': 'error', 'message': 'المتجر غير مشترك بالخدمة.'}, status=400)

        flow_form = FlowForm(request.POST, instance=flow)
        if flow_form.is_valid():
            steps_data = request.POST.get('steps', '')
            

            
            try:
                steps = validate_steps_data(steps_data)
            except ValidationError as e:
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'type': 'error', 'message': str(e)}, status=400)

            
            # Check if steps are empty when status is 'active'
            if not steps and request.POST.get('status') == 'active':
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'type': 'error', 'message': 'عليك اضافة خطوة على الاقل.'}, status=400)

            
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
                                raise ValidationError('اجراء التأخير يتطلب مدة تأخير صالحة.')
                            if content.get('delay_type') not in ['hours', 'days', 'minutes']:
                                raise ValidationError('اختيار نوع التأخير غير صالح. يجب أن يكون "ساعات" أو "أيام".')
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
                                raise ValidationError('اجراء الكوبون يتطلب مبلغ صالح.')
                            if content.get('type') not in ['fixed', 'percentage']:
                                raise ValidationError('اختيار نوع الكوبون غير صالح. يجب أن يكون "مبلغ ثابت" أو "نسبة مئوية".')
                            TextConfig.objects.filter(flow_step=step).delete()
                            CouponConfig.objects.update_or_create(
                                flow_step=step,
                                defaults={
                                    'type': content.get('type'),
                                    'amount': content.get('amount'),
                                    'maximum_amount': content.get('maximum_amount'),
                                    'expire_in': content.get('expire_in'),
                                    'free_shipping': content.get('free_shipping'),
                                    'exclude_sale_products': content.get('exclude_sale_products'),
                                    'message': content.get('message')
                                }
                            )

                        existing_steps_ids.append(step.id)

                    FlowStep.objects.filter(flow=flow).exclude(id__in=existing_steps_ids).delete()

                if FlowStep.objects.filter(flow=flow).exists():
                    flow.status = status
                    flow.save(update_fields=['status'])
                    
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'success': True, 'redirect_url': reverse('flows'), 'message': 'تم تحديث الأتمتة بنجاح.', 'type': 'success'})
                else:
                    return JsonResponse({'success': True, 'redirect_url': reverse('flows'), 'message': 'تم تحديث الأتمتة بنجاح.', 'type': 'success'})
            except (ValidationError, IntegrityError, PermissionDenied) as e:
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'type': 'error', 'message': str(e)}, status=400)
               
        else:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'type': 'error', 'message': flow_form.message}, status=400)
            else:
                return JsonResponse({'success': False, 'type': 'error', 'message': flow_form.message}, status=400)

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
    if request.method == 'POST':
        try:
            flow = get_object_or_404(Flow, id=flow_id, owner=request.user)
            flow.status = 'deleted'
            flow.save(update_fields=['status'])
            return JsonResponse({'success': True, 'message': 'تم حذف الأتمتة بنجاح.', 'type': 'success'})
        except Flow.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'الأتمتة غير موجودة.', 'type': 'error'})

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
                
                try:
                    # Update the text config
                    if suggested_step.action_type.name == 'sms':
                        text_config = new_step.text_config  # This already exists due to the signal
                        suggested_text_config = suggested_step.suggested_text_config
                        if text_config and suggested_text_config:
                            logger.info(f"Updating text config for step {new_step.id}")
                            text_config.message = suggested_text_config.message
                            text_config.save()
                    
                    # Update the delay config
                    elif suggested_step.action_type.name == 'delay':
                        delay_config = new_step.time_delay_config  # This already exists due to the signal
                        suggested_delay_config = suggested_step.suggested_time_delay_config
                        if delay_config and suggested_delay_config:
                            logger.info(f"Updating delay config for step {new_step.id}")
                            delay_config.delay_time = suggested_delay_config.delay_time
                            delay_config.delay_type = suggested_delay_config.delay_type
                            delay_config.save()
                    
                    # Update the coupon config
                    elif suggested_step.action_type.name == 'coupon':
                        coupon_config = new_step.coupon_config  # This already exists due to the signal
                        suggested_coupon_config = suggested_step.suggested_coupon_config
                        if coupon_config and suggested_coupon_config:
                            logger.info(f"Updating coupon config for step {new_step.id}")
                            coupon_config.type = suggested_coupon_config.type
                            coupon_config.amount = suggested_coupon_config.amount
                            coupon_config.expire_in = suggested_coupon_config.expire_in
                            coupon_config.maximum_amount = suggested_coupon_config.maximum_amount
                            coupon_config.free_shipping = suggested_coupon_config.free_shipping
                            coupon_config.exclude_sale_products = suggested_coupon_config.exclude_sale_products
                            coupon_config.message = suggested_coupon_config.message
                            coupon_config.save()
                            
                    else:
                        logger.warning(f"No configuration found for step {suggested_step.id}")
                        
                except Exception as step_error:
                    logger.error(f"Error updating config for step {new_step.id}: {str(step_error)}")
                    raise
                    
            
            return JsonResponse({'success': True, 'redirect_url': reverse('flow', kwargs={'flow_id': new_flow.id})})

    except SuggestedFlow.DoesNotExist:
        logger.error(f"Suggested flow {suggestion_id} does not exist")
        return JsonResponse({'success': False, 'message': 'الأتمتة الموصى بها غير موجودة.', 'type': 'error'})
    except User.DoesNotExist:
        logger.error(f"User {request.user.id} does not exist")
        return JsonResponse({'success': False, 'message': 'المستخدم غير موجود.', 'type': 'error'})
    except UserStoreLink.DoesNotExist:
        logger.error(f"User {request.user.id} is not linked to a store")
        return JsonResponse({'success': False, 'message': 'المستخدم غير مرتبط بمتجر.', 'type': 'error'})
    except Exception as e:
        logger.error(f"Error activating suggested flow: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'message': 'حدث خطاء في تنشيط الأتمتة الموصى بها. يرجى المحاولة مره اخرى.', 'type': 'error'})
            
        
