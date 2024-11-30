from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from automations.whatsapp_api import whatsapp_create_session, whatsapp_details, get_session_status, logout_user, stop_session
from base.decorators import check_token_validity
from base.models import UserStoreLink
import logging

logger = logging.getLogger(__name__)



@login_required(login_url='login')
@check_token_validity
def whatsapp_session(request, context=None):
    if context is None:
        context = {}

    try:
        # Get store data if it exists
        store_link = UserStoreLink.objects.select_related('store').get(user=request.user)
        store = store_link.store
        
        context.update({
            'store': store,
        })

    except UserStoreLink.DoesNotExist:
        logger.error(f"No store linked to your account")
        return JsonResponse({'success': False, 'type': 'error', 'message': 'لا يوجد متجر مرتبط بهذا المستخدم'}, status=404)
    except Exception as e:
        logger.error(f"Error in dashboard view: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

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
                'about': results.get('about'),
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
        