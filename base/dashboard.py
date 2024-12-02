from django.shortcuts import render,redirect
from django.contrib.auth import authenticate
from celery.exceptions import CeleryError
from django.contrib import messages
from django.db import transaction
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from . models import User, Store, UserStoreLink, Campaign, Flow, Customer, Group,ActivityLog
from django.http import JsonResponse
from django.utils.crypto import get_random_string
from Risalabot.celery import app as celery_app
from . decorators import check_token_validity
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


@login_required(login_url='login')
@check_token_validity
def dashboard_view(request, context=None):
    # Ensure context is properly passed and not overwritten
    if context is None:
        context = {}

    # Initialize default values for context
    context.update({
        'store': None,  # Default store is None
    })

    try:
        # Try to fetch the store linked to the user
        store_link = UserStoreLink.objects.select_related('store').get(user=request.user)
        store = store_link.store
        
        # Add the store to the context for use in the template
        context['store'] = store

    except UserStoreLink.DoesNotExist:
        logger.error(f"No store linked to user {request.user.id}")
        context.update({
            'error_message': "لم يتم ربط المتجر بحسابك. يرجى ربط المتجر أولا."
        })
        return render(request, 'base/dashboard.html', context)

    except Exception as e:
        logger.error(f"Unexpected error in dashboard view for user {request.user.id}: {str(e)}")
        return render(request, 'base/error_page.html', {'error_message': str(e)})

    return render(request, 'base/dashboard.html', context)



def get_dashboard_data(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            start_date_str = data.get('start')
            end_date_str = data.get('end')
            chart_type = data.get('chart', 'All')

            # Convert the date strings to datetime.date objects
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else None
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else None

            # Fetch and filter logs based on the date range and chart type
            store = UserStoreLink.objects.get(user=request.user).store
            activity_log = ActivityLog.objects.filter(store=store)
            message_log = []
            purchase_log = []
            click_log = []
            custom_log = []
            

            for log in activity_log:
                    
                if start_date and end_date and start_date <= log.date <= end_date:
                    source_type = dict(ActivityLog.SOURCE_TYPE_CHOICES).get(log.source_type, log.source_type)
                    activity_type = dict(ActivityLog.ACTIVITY_TYPE_CHOICES).get(log.activity_type, log.activity_type)
                    log_data = {
                        'date': log.date,
                        'activity_type': log.activity_type,
                        'source_type': log.source_type,
                        'activity_type_display': activity_type,
                        'source_type_display': source_type,
                        'count': log.count,                        
                    }
                    if chart_type == 'All':
                        custom_log_data = log_data.copy()  # Use original log data
                        custom_log_data['name'] = Campaign.objects.get(id=log.source_id).name if log.source_type == 'campaign' else Flow.objects.get(id=log.source_id).name
                        custom_log_data['uuid'] = log.source_id
                        custom_log.append(custom_log_data)
                        
                        if log.activity_type == 'message':
                            # Check for existing entry by date and source_type
                            existing_entry = next((entry for entry in message_log if entry['date'] == log.date and entry['source_type'] == log.source_type and entry['activity_type'] == log.activity_type), None)
                            if existing_entry:
                                existing_entry['count'] += log.count
                            else:
                                message_log.append(log_data)
                        elif log.activity_type == 'purchase':
                            # Check for existing entry by date and source_type
                            existing_entry = next((entry for entry in purchase_log if entry['date'] == log.date and entry['source_type'] == log.source_type and entry['activity_type'] == log.activity_type), None)
                            if existing_entry:
                                existing_entry['count'] += log.count
                            else:
                                purchase_log.append(log_data)
                        elif log.activity_type == 'click':
                            # Check for existing entry by date and source_type
                            existing_entry = next((entry for entry in click_log if entry['date'] == log.date and entry['source_type'] == log.source_type and entry['activity_type'] == log.activity_type), None)
                            if existing_entry:
                                existing_entry['count'] += log.count
                            else:
                                click_log.append(log_data)
                        
                        
                        
                        
                            
                    elif chart_type == 'Custom':
                        log_data['name'] = Campaign.objects.get(id=log.source_id).name if log.source_type == 'campaign' else Flow.objects.get(id=log.source_id).name
                        log_data['uuid'] = log.source_id
                        custom_log.append(log_data)
                        
                        
                    elif chart_type == 'Message' and log.activity_type == 'message':
                        # Check for existing entry by date and source_type
                        existing_entry = next((entry for entry in message_log if entry['date'] == log.date and entry['source_type'] == log.source_type and entry['activity_type'] == log.activity_type  ), None)
                        if existing_entry:
                            existing_entry['count'] += log.count
                        else:
                            message_log.append(log_data)
                    elif chart_type == 'Purchase' and log.activity_type == 'purchase':
                        # Check for existing entry by date and source_type
                        existing_entry = next((entry for entry in purchase_log if entry['date'] == log.date and entry['source_type'] == log.source_type and entry['activity_type'] == log.activity_type), None)
                        if existing_entry:
                            existing_entry['count'] += log.count
                        else:
                            purchase_log.append(log_data)
                    elif chart_type == 'Click' and log.activity_type == 'click':
                        # Check for existing entry by date and source_type
                        existing_entry = next((entry for entry in click_log if entry['date'] == log.date and entry['source_type'] == log.source_type and entry['activity_type'] == log.activity_type), None)
                        if existing_entry:
                            existing_entry['count'] += log.count
                        else:
                            click_log.append(log_data)

            # Prepare the data to be returned
            name_to_uuid = {log['name']: (log['uuid'], log['source_type_display']) for log in custom_log}
            activity_dropdown_menu_types = [choice[1] for choice in ActivityLog.ACTIVITY_TYPE_CHOICES]
            source_dropdown_menu_types = [choice[1] for choice in ActivityLog.SOURCE_TYPE_CHOICES]
            response_data = {
                'success': True,
                'data': {
                    'message_count': store.total_messages_sent,
                    'purchases': store.total_purchases,
                    'total_customers': store.total_customers,
                    'clicks': store.total_clicks,
                    'active_automations': Flow.objects.filter(owner=request.user, status='active').count() + Campaign.objects.filter(store=store, status='scheduled').count(),
                    'message_log': message_log,
                    'purchase_log': purchase_log,
                    'click_log': click_log,
                    'custom_log': custom_log,
                    'activityDropdownMenuTypes': activity_dropdown_menu_types,
                    'sourceDropdownMenuTypes': source_dropdown_menu_types,
                    'nameDropdownMenuTypes': name_to_uuid,
                }
            }
            
                        
    

            return JsonResponse(response_data, status=200)

        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'Invalid JSON'}, status=400)
        except Exception as e:
            # Catch any other exceptions and return a response
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
    else:
        return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=405)