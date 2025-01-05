from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from automations.whatsapp_api import whatsapp_create_session, whatsapp_details, get_session_status, logout_user, stop_session, start_session, delete_session, get_qr_code
from base.decorators import check_token_validity, rate_limit
from base.models import UserStoreLink, Notification
from django.shortcuts import redirect
import logging

logger = logging.getLogger(__name__)




@login_required(login_url='login')
@check_token_validity
def whatsapp_session(request, context=None):
    # Use the context passed from the decorator (don't re-initialize it)
    if context is None:
        context = {}

    try:
        # Try to fetch the store linked to the user
        store = UserStoreLink.objects.get(user=request.user).store
        context['store'] = store  # Add store to context
        context['notification_count'] = Notification.objects.filter(store=store).count()
        context['notifications'] = Notification.objects.filter(store=store).order_by('-created_at')
    except UserStoreLink.DoesNotExist:
        logger.error(f"No store linked to user {request.user.id}")
        return redirect('dashboard')  # Redirect to dashboard if no store linked

    # Continue with rendering the template if the store exists
    return render(request, 'base/whatsapp_session.html', context)


@login_required(login_url='login')
@rate_limit(key_prefix='whatsapp_session', limit=20, period=60)
def manage_whatsapp_session(request):
    """
    Single endpoint to handle WhatsApp session:
    - Checks status
    - Returns either QR code or WhatsApp details
    - Handles session creation when needed
    """
    try:
        user = request.user
        status = get_session_status(user.session_id)
        
        if status == "WORKING":
            # Session active and connected - return details
            user.connected = True
            user.save()
            results = whatsapp_details(user)
            
            if results:
                return JsonResponse({
                    'success': True,
                    'qr': False,  # Signal to show details container
                    'data': {
                        'id': results.get('id'),
                        'name': results.get('name'),
                        'profile_picture': results.get('profile_picture')
                    }
                })
            else:
                raise Exception("Failed to fetch WhatsApp details")

        elif status == "SCAN_QR_CODE":
            # Need to scan QR - return QR code
            user.connected = False
            user.save()
            qr_code = get_qr_code(user.session_id)
            
            if qr_code['success']:
                return JsonResponse({
                    'success': True,
                    'qr': True,  # Signal to show QR container
                    'data': {'qr': qr_code['qr']}
                })
            else:
                raise Exception("Failed to get QR code")

        elif status == "FAILED":
            # Clean up failed session and start new one
            delete_session(user)
            success = whatsapp_create_session(user)
            if success:
                qr_code = get_qr_code(user.session_id)
                if qr_code['success']:
                    return JsonResponse({
                        'success': True,
                        'qr': True,
                        'data': {'qr': qr_code['qr']}
                    })
            raise Exception("Failed to create new session after failure")

        elif status == "NOT_FOUND":
            # Start new session and return QR
            user.connected = False
            user.save()
            success = whatsapp_create_session(user)
            
            if success:
                qr_code = get_qr_code(user.session_id)
                if qr_code['success']:
                    return JsonResponse({
                        'success': True,
                        'qr': True,
                        'data': {'qr': qr_code['qr']}
                    })
            raise Exception("Failed to create new session")

        else:
            raise Exception("Unknown session status")
            logger.error(f"Unknown session status: {status}")

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)


       
    
@login_required(login_url='login')
def stop_whatsapp(request):
    if request.method == 'POST':
        result = stop_session(request.user)
        if result['success']:
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False})
        