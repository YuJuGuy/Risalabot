from django.shortcuts import render,redirect
from django.contrib.auth import authenticate
from celery.exceptions import CeleryError
from django.contrib import messages
from django.db import transaction
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from . models import User, Store, UserStoreLink, Campaign, Flow, Customer, Group,ActivityLog, Notification
from django.http import JsonResponse
from django.utils.crypto import get_random_string
from Risalabot.celery import app as celery_app
from . decorators import check_token_validity
import json
import logging
from datetime import datetime
from django.db import connection
from django.db.models import Prefetch

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
        'notifications': None,  # Initialize notifications
        'notification_count': 0  # Initialize notification count
    })

    try:
        # Try to fetch the store linked to the user
        store_link = UserStoreLink.objects.select_related('store').get(user=request.user)
        store = store_link.store
        
        # Add the store to the context for use in the template


        context['store'] = store
        context['notification_count'] = Notification.objects.filter(store=store).count()
        context['notifications'] = Notification.objects.filter(store=store).order_by('-created_at')


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



from collections import defaultdict

@login_required
def get_dashboard_data(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            start_date_str = data.get('start')
            end_date_str = data.get('end')
            chart_type = data.get('chart', 'All')

            # Parse dates
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else None
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else None

            # Get store
            store = UserStoreLink.objects.select_related('store').get(user=request.user).store

            # Base queryset for activity logs
            activity_log_queryset = ActivityLog.objects.filter(store=store)

            # Apply date filter
            if start_date and end_date:
                activity_log_queryset = activity_log_queryset.filter(date__range=(start_date, end_date))

            # Pre-fetch Campaign and Flow data
            campaign_names = {c.id: c.name for c in Campaign.objects.filter(store=store)}
            flow_names = {f.id: f.name for f in Flow.objects.filter(store=store)}
            source_name_map = {**campaign_names, **flow_names}

            # Initialize logs
            message_log = []
            purchase_log = []
            click_log = []
            custom_log = []

            # Helper function to add logs
            def add_log(log_list, log, log_data):
                existing_entry = next(
                    (entry for entry in log_list if entry['date'] == log.date and entry['source_type'] == log.source_type),
                    None,
                )
                if existing_entry:
                    existing_entry['count'] += log.count
                else:
                    log_list.append(log_data)

            # Map choices for display
            source_type_display = dict(ActivityLog.SOURCE_TYPE_CHOICES)
            activity_type_display = dict(ActivityLog.ACTIVITY_TYPE_CHOICES)

            # Process logs
            for log in activity_log_queryset:
                log_data = {
                    'date': log.date,
                    'activity_type': log.activity_type,
                    'source_type': log.source_type,
                    'activity_type_display': activity_type_display.get(log.activity_type, log.activity_type),
                    'source_type_display': source_type_display.get(log.source_type, log.source_type),
                    'count': log.count,
                }

                # Add custom log data
                if log.source_id in source_name_map:
                    log_data['name'] = source_name_map[log.source_id]
                    log_data['uuid'] = log.source_id
                    custom_log.append(log_data)

                # Add to specific logs based on activity type
                if chart_type in ['All', 'Message'] and log.activity_type == 'message':
                    add_log(message_log, log, log_data)
                elif chart_type in ['All', 'Purchase'] and log.activity_type == 'purchase':
                    add_log(purchase_log, log, log_data)
                elif chart_type in ['All', 'Click'] and log.activity_type == 'click':
                    add_log(click_log, log, log_data)

            # Prepare response data
            name_to_uuid = {log['name']: (log['uuid'], log['source_type_display']) for log in custom_log}
            response_data = {
                'success': True,
                'data': {
                    'message_count': store.total_messages_sent,
                    'purchases': store.total_purchases,
                    'total_customers': store.total_customers,
                    'clicks': store.total_clicks,
                    'active_automations': Flow.objects.filter(owner=request.user, status='active').count()
                                          + Campaign.objects.filter(store=store, status='scheduled').count(),
                    'message_log': message_log,
                    'purchase_log': purchase_log,
                    'click_log': click_log,
                    'custom_log': custom_log,
                    'activityDropdownMenuTypes': [choice[1] for choice in ActivityLog.ACTIVITY_TYPE_CHOICES],
                    'sourceDropdownMenuTypes': [choice[1] for choice in ActivityLog.SOURCE_TYPE_CHOICES],
                    'nameDropdownMenuTypes': name_to_uuid,
                }
            }

            return JsonResponse(response_data, status=200)

        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'Invalid JSON'}, status=400)
        except Exception as e:
            logger.exception("Error in get_dashboard_data")
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
    else:
        return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=405)
