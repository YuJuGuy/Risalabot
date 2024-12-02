from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from automations.whatsapp_api import whatsapp_create_session, whatsapp_details, get_session_status, logout_user, stop_session
from base.decorators import check_token_validity
from base.models import UserStoreLink
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
    except UserStoreLink.DoesNotExist:
        logger.error(f"No store linked to user {request.user.id}")
        return redirect('dashboard')  # Redirect to dashboard if no store linked

    # Continue with rendering the template if the store exists
    return render(request, 'base/whatsapp_session.html', context)


@login_required(login_url='login')
def create_whatsapp_session(request):
    try:
        user = request.user
        status = get_session_status(user.session_id)
        if status == "WORKING":
            user.connected = True
            user.save()
        else:
            user.connected = False
            user.save()    
    
        return JsonResponse({'success': True, 'data': {'is_connected': user.connected}})
    except Exception as e:
        return JsonResponse({'success': False, 'type': 'error', 'message': str(e)}, status=500)

@login_required(login_url='login')
def get_whatsapp_qr_code(request):
    try:
        result = whatsapp_create_session(request.user)
        response_data = {
            'success': result['success'],
            'message': result.get('message', '')
        }
        if 'qr' in result:
            response_data['qr'] = result['qr']
        return JsonResponse(response_data)
    except Exception as e:
        print(e)
        return JsonResponse({'success': False, 'message': 'An error occurred', 'error': str(e)})
    

@login_required(login_url='login')
def get_whatsapp_details(request):
    user = request.user
    try:
        results = whatsapp_details(user)

        if results:

            return JsonResponse({
                'id': results.get('id'),
                'name': results.get('name'),
                'profile_picture': results.get('profile_picture')

            })
        else:
            return JsonResponse({'success': False, 'type': 'error', 'message': 'خطأ في جلب بيانات الواتساب'}, status=500)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
    

    
    
@login_required(login_url='login')
def stop_whatsapp(request):
    if request.method == 'POST':
        result = stop_session(request.user)
        if result['success']:
            request.user.connected = False
            request.user.save()
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False})
        