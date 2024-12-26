from .models import Campaign, UserStoreLink, Group, Customer, Notification
from .forms import CampaignForm
from .decorators import check_token_validity
from django.shortcuts import render, redirect
from django.urls import reverse
from django.http import JsonResponse
from django.utils.timezone import make_aware
from datetime import datetime
from automations.tasks import send_whatsapp_message_task
from Risalabot.celery import app as celery_app
from celery.exceptions import CeleryError
from django.contrib import messages
from django.contrib.auth.decorators import login_required
import threading
from django.core.exceptions import ObjectDoesNotExist

from .Utils.data_utils import sync_data


import logging

logger = logging.getLogger(__name__)




def validate_campaign_data(campaign_data, request):
    try:
        # Validate the message
        if 'msg' not in campaign_data or not campaign_data['msg'].strip():
            return JsonResponse({'success': False, 'type': 'error', 'message': 'يرجى كتابة الرسالة.'}, status=400)

        # Validate customers group
        if 'customers_group' not in campaign_data or not campaign_data['customers_group'].strip() or campaign_data['customers_group'] == 'اختر مجموعة العملاء':
            return JsonResponse({'success': False, 'type': 'error', 'message': 'يرجى تحديد مجموعة صالحة.'}, status=400)

        # Ensure the group exists in the user's store
        valid_groups = [group.group_id for group in Group.objects.filter(store=UserStoreLink.objects.get(user=request.user).store)]
        # Ensure the group ID is compared as the same type
        try:
            group_id = int(campaign_data['customers_group'])  # Convert to integer if possible
        except ValueError:
            return JsonResponse({'success': False, 'type': 'error', 'message': 'مجموعة العملاء غير موجودة.'}, status=400)

        if group_id not in valid_groups:
            return JsonResponse({'success': False, 'type': 'error', 'message': 'مجموعة العملاء غير موجودة.'}, status=400)

        # Validate scheduled time
        # Check if 'scheduled_time' is provided
        if 'scheduled_time' not in campaign_data or not campaign_data['scheduled_time']:
            return JsonResponse({'success': False, 'type': 'error', 'message': 'يرجى تحديد وقت المخطط.'}, status=400)

        # Parse and validate the scheduled time
        if isinstance(campaign_data['scheduled_time'], str):
            if not campaign_data['scheduled_time'].strip():  # Strip only if it's a string
                return JsonResponse({'success': False, 'type': 'error', 'message': 'يرجى تحديد وقت المخطط.'}, status=400)
            try:
                scheduled_time = datetime.fromisoformat(campaign_data['scheduled_time'].strip())
            except ValueError:
                return JsonResponse({'success': False, 'type': 'error', 'message': 'تنسيق الوقت المخطط غير صحيح.'}, status=400)
        else:
            scheduled_time = campaign_data['scheduled_time']

        # Ensure the scheduled time is timezone-aware
        if scheduled_time.tzinfo is None or scheduled_time.tzinfo.utcoffset(scheduled_time) is None:
            scheduled_time = make_aware(scheduled_time)

        # Check if the scheduled time is in the past
        if scheduled_time < make_aware(datetime.now()):
            return JsonResponse({'success': False, 'type': 'error', 'message': 'لا يمكن أن يكون الوقت المخطط في الماضي.'}, status=400)


        # Validate status
        if campaign_data['status'] not in ['scheduled', 'draft']:
            return JsonResponse({'success': False, 'type': 'error', 'message': 'يرجى تحديد حالة صالحة.'}, status=400)

        # Validate delay in seconds
        if 'delay_in_seconds' not in campaign_data or not str(campaign_data['delay_in_seconds']).strip():
            return JsonResponse({'success': False, 'type': 'error', 'message': 'يرجى تحديد التاخير بين الرسائل بالثواني.'}, status=400)
        if not str(campaign_data['delay_in_seconds']).isdigit():
            return JsonResponse({'success': False, 'type': 'error', 'message': 'يرجى إدخال رقم صحيح للتأخير.'}, status=400)
        if int(campaign_data['delay_in_seconds']) < 0:
            return JsonResponse({'success': False, 'type': 'error', 'message': 'التاخير بين الرسائل يجب ان يكون قيمة موجبة.'}, status=400)

        # Return None if no errors
        return None

    except Exception as e:
        return JsonResponse({'success': False, 'type': 'error', 'message': f'خطأ في التحقق من البيانات: {str(e)}'}, status=400)





@login_required(login_url='login')
@check_token_validity
def campaign(request, context=None):
    
    if context is None:
        context = {}

    try:
        user_store_link = UserStoreLink.objects.get(user=request.user)
        store = user_store_link.store
        store_groups = Group.objects.filter(store=store).order_by('-group_id')
        context['notification_count'] = Notification.objects.filter(store=store).count()
        context['notifications'] = Notification.objects.filter(store=store).order_by('-created_at')

        if not store_groups:
            messages.info(request, 'لا يوجد عملاء او مجموعات في المتجر. يرجى تحديث البيانات.') 
            
    except UserStoreLink.DoesNotExist:
        return redirect('dashboard')
    except Exception as e:
        return JsonResponse({'success': False, 'type': 'error', 'message': f'خطاء في البيانات: {str(e)}', 'redirect_url': reverse('dashboard')}, status=400)


    if request.method == 'POST':
        form = CampaignForm(request.POST, store_groups=store_groups)
        if form.is_valid():

            validation_response = validate_campaign_data(form.cleaned_data, request)
            if validation_response is not None:
                return validation_response

            msg = form.cleaned_data['msg']
            status = form.cleaned_data['status']
            group_id = form.cleaned_data['customers_group']
            delay_in_seconds = form.cleaned_data['delay_in_seconds']
            scheduled_time = form.cleaned_data['scheduled_time']

            # Only perform the additional validations if the status is 'active'
            if status == 'scheduled':
                if scheduled_time.tzinfo is None or scheduled_time.tzinfo.utcoffset(scheduled_time) is None:
                    scheduled_time = make_aware(scheduled_time)
                if scheduled_time < make_aware(datetime.now()):
                    return JsonResponse({'success': False, 'type': 'error', 'message': 'لا يمكن أن يكون الوقت المخطط في الماضي.'}, status=400)
                # Fetch customers only for active campaigns
                customers_data = Customer.objects.filter(customer_groups__group_id=group_id)
                customers_numbers = [customer.customer_phone for customer in customers_data]

                # Convert customers_data to a list of dictionaries for JSON serialization
                customers_data_serialized = [
                    {
                        'first_name': customer.customer_first_name,
                        'name': customer.customer_name,
                        'email': customer.customer_email,
                        'phone': customer.customer_phone,
                        'location': customer.customer_location,
                    }
                    for customer in customers_data
                ]

                if len(customers_data) == 0:
                    return JsonResponse({'success': False, 'type': 'error', 'message': 'لا يوجد أي عملاء في المجموعة المختارة.'}, status=400)

                # Check if the message limit is sufficient
                if not store.subscription or len(customers_numbers) > store.subscription.messages_limit - store.subscription_message_count:
                    return JsonResponse({'success': False, 'type': 'error', 'message': 'لا يوجد رصيد كافي لانشاء هذه الحملة.'}, status=400)
            else:
                # Set customers_data and customers_numbers to empty if it's a draft
                customers_data_serialized = []
                customers_numbers = []

            # Save the campaign and get the campaign ID
            campaign = form.save(commit=False)
            campaign.status = status
            campaign.store = store
            campaign.scheduled_time = scheduled_time
            campaign.save()
            
            data = {
                'customers_data': customers_data_serialized,  # Use the serialized data
                'msg': msg,
                'delay_in_seconds': delay_in_seconds,
                'store_id': store.store_id,
                'campaign_id': campaign.id
            }


            # Create a list with 150 copies of the yousefdata dictionary

            # Schedule the task only if the status is 'scheduled'
            if status == 'scheduled':
                # Schedule the task to send messages at the scheduled time
                task = send_whatsapp_message_task.apply_async(args=[data], eta=scheduled_time)
                campaign.task_id = task.id
                campaign.save()
                return JsonResponse({'success': True, 'type': 'success', 'message': 'تم إنشاء الحملة وتم حفظها بنجاح.', 'redirect_url': reverse('campaigns')})
            else:
                return JsonResponse({'success': True, 'type': 'success', 'message': 'تم إنشاء الحملة وتم حفظها بنجاح.', 'redirect_url': reverse('campaigns')})

        else:
            error_messages = form.get_custom_errors()
            return JsonResponse({'success': False, 'type': 'error', 'message': error_messages}, status=400)
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
        
        # Only allow editing if the campaign is 'scheduled' or 'draft'
        if campaign.status not in ['scheduled', 'draft']:
            return JsonResponse({'success': False, 'type': 'error', 'message': 'لا يمكن تحديث هذه الحملة لأنها غير مخططة أو مسودة.'}, status=400)
        
        # Store the original status before handling the form submission
        original_status = campaign.status

        store_groups = Group.objects.filter(store=store).order_by('-group_id')

        if request.method == 'POST':
            form = CampaignForm(request.POST, instance=campaign, store_groups=store_groups)
            if form.is_valid():
                # Update campaign with form data but don't save yet
                validation_response = validate_campaign_data(form.cleaned_data, request)
                if validation_response is not None:
                    return validation_response

                campaign = form.save(commit=False)
                new_status = form.cleaned_data['status']
                scheduled_time = form.cleaned_data['scheduled_time']
                group_id = form.cleaned_data['customers_group']
                msg = form.cleaned_data['msg']
                delay_in_seconds = form.cleaned_data['delay_in_seconds']

                # If the new status is 'draft' and the original status was 'scheduled', revoke the task
                if new_status == 'draft' and original_status == 'scheduled' and campaign.task_id:
                    celery_app.control.revoke(campaign.task_id, terminate=True)
                    campaign.task_id = None  # Clear the task ID if the campaign is no longer scheduled
                    campaign.status = 'draft'  # Update the status to 'draft'
                    campaign.save()  # Save the changes
                    return JsonResponse({'success': True, 'type': 'success', 'message': 'تم إلغاء المهمة وحفظ الحملة كمسودة.'})
                    
                # If the status is 'scheduled', validate and reschedule
                elif new_status == 'scheduled':
                    # Revoke the old task if it exists
                    if original_status == 'scheduled' and campaign.task_id:
                        celery_app.control.revoke(campaign.task_id, terminate=True)
                    
                    # Ensure scheduled_time is timezone-aware and in the future
                    if scheduled_time.tzinfo is None or scheduled_time.tzinfo.utcoffset(scheduled_time) is None:
                        scheduled_time = make_aware(scheduled_time)
                    if scheduled_time < make_aware(datetime.now()):
                        return JsonResponse({'success': False, 'type': 'error', 'message': 'لا يمكن أن يكون الوقت المخطط في الماضي.'}, status=400)
                    
                    # Fetch customers for the selected group
                    customers_data = Customer.objects.filter(customer_groups__group_id=group_id)
                    customers_numbers = [customer.customer_phone for customer in customers_data]

                    # Convert customers_data to a list of dictionaries for JSON serialization
                    customers_data_serialized = [
                        {
                            'first_name': customer.customer_first_name,
                            'name': customer.customer_name,
                            'email': customer.customer_email,
                            'phone': customer.customer_phone,
                            'location': customer.customer_location,
                        }
                        for customer in customers_data
                    ]

                    if len(customers_numbers) == 0:
                        return JsonResponse({'success': False, 'type': 'error', 'message': 'لا يوجد أي عملاء في المجموعة المختارة.'}, status=400)
                    
                    # Check if the message limit is sufficient
                    if not store.subscription or len(customers_numbers) > store.subscription.messages_limit - store.subscription_message_count:
                        return JsonResponse({'success': False, 'type': 'error', 'message': 'لا يوجد رصيد كافي لانشاء هذه الحملة.'}, status=400)
                    
                    data = {
                        'customers_data': customers_data_serialized,
                        'msg': msg,
                        'delay_in_seconds': delay_in_seconds,
                        'store_id': store.store_id,
                        'campaign_id': campaign.id
                    }

                    # Schedule the task with the new time
                    task = send_whatsapp_message_task.apply_async(eta=scheduled_time, args=[data])
                    
                    # Update the campaign's task_id and status to 'scheduled'
                    campaign.task_id = task.id
                    campaign.status = 'scheduled'
                    campaign.scheduled_time = scheduled_time
                    campaign.save()  # Save the changes
                    return JsonResponse({'success': True, 'type': 'success', 'message': 'تم تحديث الحملة وإعادة حفظها بنجاح.'})
                
                # Save the campaign changes, including the message and other fields
                campaign.save()
                return JsonResponse({'success': True, 'type': 'success', 'message': 'تم حفظ الحملة كمسودة.'})
            else:
                return JsonResponse({'success': False, 'type': 'error', 'message': 'البيانات غير موجودة.'}, status=400)

    except Campaign.DoesNotExist:
        return JsonResponse({'success': False, 'type': 'error', 'message': 'الحملة غير موجودة.', 'redirect_url': reverse('campaigns')}, status=400)
    except UserStoreLink.DoesNotExist:
        return JsonResponse({'success': False, 'type': 'error', 'message': 'لم يتم ربط المتجر. يرجى ربط متجر أولا.', 'redirect_url': reverse('dashboard')}, status=400)
    
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
        # Fetch the store associated with the user
        store = UserStoreLink.objects.select_related('store').get(user=request.user).store

        if campaign_id:
            # Fetch a specific campaign
            campaign = Campaign.objects.filter(id=campaign_id, store=store).select_related('store').first()
            if not campaign:
                return JsonResponse({'success': False, 'type': 'error', 'error': 'لم يتم العثور على الحملة.'}, status=404)

            data = {
                'name': campaign.name,
                'scheduled_time': campaign.scheduled_time.strftime('%Y-%m-%d %H:%M'),  # Adjust format as needed
                'customers_group': campaign.customers_group,
                'status': campaign.status,
                'status_display': dict(Campaign.status_choices).get(campaign.status, campaign.status),
                'msg': campaign.msg,
                'delay_in_seconds': campaign.delay_in_seconds,
                'edit_url': reverse('edit_campaign', args=[campaign.id]),  # Edit campaign URL
                'delete_url': reverse('campaign_delete', args=[campaign.id])  # Delete campaign URL
            }
            return JsonResponse({'success': True, 'data': data}, status=200)
        else:
            # Fetch all campaigns for the store
            campaigns = Campaign.objects.filter(
                store=store, 
                status__in=['scheduled', 'failed', 'sent', 'draft', 'cancelled']
            ).select_related('store').order_by('-scheduled_time')

            # Prepare data for all campaigns
            data = [{
                'id': campaign.id,
                'name': campaign.name,
                'scheduled_time': campaign.scheduled_time.strftime('%Y-%m-%d %H:%M'),  # Adjust format as needed
                'messages_sent': campaign.messages_sent,
                'status': campaign.status,
                'status_display': dict(Campaign.status_choices).get(campaign.status, campaign.status),
                'edit_url': reverse('edit_campaign', args=[campaign.id]),  # Edit campaign URL
                'delete_url': reverse('campaign_delete', args=[campaign.id]),  # Delete campaign URL
                'cancel_url': reverse('campaign_cancel', args=[campaign.id])  # Cancel campaign URL
            } for campaign in campaigns]

            return JsonResponse({'success': True, 'data': data}, status=200)

    except ObjectDoesNotExist:
        logger.error(f"Campaign or Store not found for user {request.user.id}")
        return JsonResponse({'success': False, 'type': 'error', 'error': 'لم يتم العثور على الحملة أو المتجر.'}, status=404)
    except Exception as e:
        logger.exception(f"Error in get_campaign_data: {str(e)}")
        return JsonResponse({'success': False, 'type': 'error', 'error': str(e)}, status=500)

    
@login_required(login_url='login')
def campaign_cancel(request, campaign_id):
    try:
        # Get the store linked to the logged-in user
        user_store = UserStoreLink.objects.get(user=request.user).store
        # Fetch the campaign belonging to the user's store
        campaign = Campaign.objects.get(id=campaign_id, store=user_store)

        # Check if the campaign is scheduled
        if campaign.status != 'scheduled':
            return JsonResponse({'success': False, 'type': 'error', 'message': 'هذه الحملة غير مخططة، لذلك لا يمكن إلغاؤها.'}, status=400)

        # Check if the campaign has a task ID (Celery task)
        if campaign.task_id:
            # Update campaign status before attempting to revoke
            campaign.status = 'cancelled'
            campaign.task_id = None
            campaign.save(update_fields=['task_id', 'status'])

            # Return response immediately for AJAX update
            response = JsonResponse({'success': True, 'type': 'success', 'message': 'تم إلغاء الحملة بنجاح.'})

            # Start a new thread to revoke the task
            threading.Thread(target=revoke_task, args=(campaign.task_id,)).start()

            return response

        else:
            campaign.status = 'cancelled'
            campaign.save(update_fields=['task_id', 'status'])
            return JsonResponse({'success': True, 'type': 'success', 'message': 'تم إلغاء الحملة بنجاح.'})
            
    except (Campaign.DoesNotExist, UserStoreLink.DoesNotExist):
        # If either the campaign or the user-store link does not exist
        return JsonResponse({'success': False, 'type': 'error', 'message': 'ليس لديك الصلاحية لإلغاء هذه الحملة.'}, status=400)



@login_required(login_url='login')
def delete_campaign(request, campaign_id):
    if request.method == 'POST':
        try:
            campaign = Campaign.objects.get(id=campaign_id, store=UserStoreLink.objects.get(user=request.user).store)
            campaign.status = 'deleted'
            campaign.save(update_fields=['status'])
            return JsonResponse({'success': True, 'type': 'success', 'message': 'تم حذف الحملة بنجاح.'})
        except Campaign.DoesNotExist:
            return JsonResponse({'success': False, 'type': 'error', 'message': 'الحملة غير موجودة.'}, status=400)
    else:
        return JsonResponse({'success': False, 'type': 'error', 'message': 'طريقة الطلب غير صالحة.'}, status=405)

def revoke_task(task_id):
    try:
        celery_app.control.revoke(task_id)
    except CeleryError as e:
        logger.error(f"فشل إلغاء المهمة: {str(e)}")
    except Exception as e:
        logger.error(f"فشل إلغاء المهمة: {str(e)}")

