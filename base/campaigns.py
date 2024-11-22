from .models import Campaign, UserStoreLink, Group, Customer
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


import logging

logger = logging.getLogger(__name__)




@login_required(login_url='login')
@check_token_validity
def campaign(request, context=None):
    if context is None:
        context = {}
    try:
        store = UserStoreLink.objects.get(user=request.user).store
        # get all groups for the store
        store_groups = Group.objects.filter(store=store).order_by('-group_id')
        
        if not store_groups:
            return JsonResponse({'success': False, 'type': 'error', 'errors': 'لا يوجد مجموعات في المتجر.'}, status=400)
        
    except UserStoreLink.DoesNotExist:
        return JsonResponse({'success': False, 'type': 'error', 'errors': 'لم يتم ربط المتجر. يرجى ربط متجر أولا.', 'redirect_url': reverse('dashboard')}, status=400)

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
                    return JsonResponse({'success': False, 'type': 'error', 'errors': 'لا يمكن أن يكون الوقت المخطط في الماضي.'}, status=400)
                # Fetch customers only for active campaigns
                customers_data = Customer.objects.filter(customer_groups__group_id=group_id)
                customers_numbers = [customer.customer_phone for customer in customers_data]

                # Convert customers_data to a list of dictionaries for JSON serialization
                customers_data_serialized = [
                    {
                        'name': customer.customer_name,
                        'email': customer.customer_email,
                        'phone': customer.customer_phone,
                        'location': customer.customer_location,
                    }
                    for customer in customers_data
                ]

                if len(customers_data) == 0:
                    return JsonResponse({'success': False, 'type': 'error', 'errors': 'لا يوجد أي عملاء في المجموعة المختارة.'}, status=400)

                # Check if the message limit is sufficient
                if len(customers_numbers) > store.subscription.messages_limit - store.subscription_message_count:
                    return JsonResponse({'success': False, 'type': 'error', 'errors': 'الرصيد الرسالي غير متاح.'}, status=400)
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
                'store_id': store.id,
                'campaign_id': campaign.id
            }

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
            return JsonResponse({'success': False, 'errors': 'لا يمكن تحديث هذه الحملة لأنها غير مخططة أو مسودة.'}, status=400)
        
        # Store the original status before handling the form submission
        original_status = campaign.status

        store_groups = Group.objects.filter(store=store).order_by('-group_id')

        if request.method == 'POST':
            form = CampaignForm(request.POST, instance=campaign, store_groups=store_groups)
            if form.is_valid():
                # Update campaign with form data but don't save yet
                campaign = form.save(commit=False)
                new_status = form.cleaned_data['status']
                scheduled_time = form.cleaned_data['scheduled_time']
                group_id = form.cleaned_data['customers_group']
                msg = form.cleaned_data['msg']

                # If the new status is 'draft' and the original status was 'scheduled', revoke the task
                if new_status == 'draft' and original_status == 'scheduled' and campaign.task_id:
                    celery_app.control.revoke(campaign.task_id, terminate=True)
                    campaign.task_id = None  # Clear the task ID if the campaign is no longer scheduled
                    campaign.status = 'draft'  # Update the status to 'draft'
                    campaign.save()  # Save the changes
                    return JsonResponse({'success': True, 'message': 'تم إلغاء المهمة وحفظ الحملة كمسودة.'})
                    
                # If the status is 'scheduled', validate and reschedule
                elif new_status == 'scheduled':
                    # Revoke the old task if it exists
                    if original_status == 'scheduled' and campaign.task_id:
                        celery_app.control.revoke(campaign.task_id, terminate=True)
                    
                    # Ensure scheduled_time is timezone-aware and in the future
                    if scheduled_time.tzinfo is None or scheduled_time.tzinfo.utcoffset(scheduled_time) is None:
                        scheduled_time = make_aware(scheduled_time)
                    if scheduled_time < make_aware(datetime.now()):
                        return JsonResponse({'success': False, 'errors': 'لا يمكن أن يكون الوقت المخطط في الماضي.'}, status=400)
                    
                    # Fetch customers for the selected group
                    customers_data = Customer.objects.filter(customer_groups__group_id=group_id)
                    customers_numbers = [customer.customer_phone for customer in customers_data]

                    # Convert customers_data to a list of dictionaries for JSON serialization
                    customers_data_serialized = [
                        {
                            'name': customer.customer_name,
                            'email': customer.customer_email,
                            'phone': customer.customer_phone,
                            'location': customer.customer_location,
                        }
                        for customer in customers_data
                    ]

                    if len(customers_numbers) == 0:
                        return JsonResponse({'success': False, 'errors': 'لا يوجد أي عملاء في المجموعة المختارة.'}, status=400)
                    
                    # Check if the message limit is sufficient
                    if len(customers_numbers) > store.subscription.messages_limit - store.subscription_message_count:
                        return JsonResponse({'success': False, 'errors': 'الرصيد الرسالي غير متاح.'}, status=400)
                    
                    data = {
                        'customers_data': customers_data_serialized,
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
                    campaign.purchases += 1
                    campaign.messages_sent += 1
                    campaign.save()  # Save the changes
                    return JsonResponse({'success': True, 'type': 'success', 'message': 'تم تحديث الحملة وإعادة حفظها بنجاح.'})
                
                # Save the campaign changes, including the message and other fields
                campaign.save()
                return JsonResponse({'success': True, 'type': 'success', 'message': 'تم حفظ الحملة كمسودة.'})
            else:
                return JsonResponse({'success': False, 'type': 'error', 'errors': 'البيانات غير موجودة.'}, status=400)

    except Campaign.DoesNotExist:
        return JsonResponse({'success': False, 'type': 'error', 'errors': 'الحملة غير موجودة.', 'redirect_url': reverse('campaigns')}, status=400)
    except UserStoreLink.DoesNotExist:
        return JsonResponse({'success': False, 'type': 'error', 'errors': 'لم يتم ربط المتجر. يرجى ربط متجر أولا.', 'redirect_url': reverse('dashboard')}, status=400)
    
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
        return JsonResponse({'success': False, 'type': 'error', 'error': 'لم يتم العثور على الحملة.'}, status=404)
    except Exception as e:
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
            return JsonResponse({'success': False, 'errors': 'هذه الحملة غير مخططة، لذلك لا يمكن إلغاؤها.'}, status=400)

        # Check if the campaign has a task ID (Celery task)
        if campaign.task_id:
            try:
                # Try to revoke the task using Celery
                celery_app.control.revoke(campaign.task_id)
            except CeleryError as e:
                # Log the error and display a user-friendly message
                logger.error(f"فشل إلغاء المهمة: {str(e)}")
                # Continue to mark the campaign as cancelled
            # If successfully revoked or if revocation fails, update campaign status
            campaign.task_id = None
            campaign.status = 'cancelled'
            campaign.save(update_fields=['task_id', 'status'])
            return JsonResponse({'success': True, 'type': 'success', 'message': 'تم إلغاء الحملة بنجاح.'})
                
        else:
            campaign.status = 'cancelled'
            campaign.save(update_fields=['task_id', 'status'])
            return JsonResponse({'success': True, 'type': 'success', 'message': 'تم إلغاء الحملة بنجاح.'})
            
    except (Campaign.DoesNotExist, UserStoreLink.DoesNotExist):
        # If either the campaign or the user-store link does not exist
        return JsonResponse({'success': False, 'type': 'error', 'errors': 'ليس لديك الصلاحية لإلغاء هذه الحملة.'}, status=400)



@login_required(login_url='login')
def delete_campaign(request, campaign_id):
    if request.method == 'POST':
        try:
            campaign = Campaign.objects.get(id=campaign_id, store=UserStoreLink.objects.get(user=request.user).store)
            campaign.status = 'deleted'
            campaign.save(update_fields=['status'])
            return JsonResponse({'success': True, 'type': 'success', 'message': 'تم حذف الحملة بنجاح.'})
        except Campaign.DoesNotExist:
            return JsonResponse({'success': False, 'type': 'error', 'errors': 'الحملة غير موجودة.'}, status=400)
    else:
        return JsonResponse({'success': False, 'type': 'error', 'errors': 'طريقة الطلب غير صالحة.'}, status=405)