from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .whatsapp_api import whatsapp_create_session, whatsapp_details, get_session_status, logout_user, stop_session


@login_required(login_url='login')
def create_whatsapp_session(request):
    status = get_session_status(request.user.session_id)
    print(status)
    if status == "WORKING":
        request.user.connected = True
        request.user.save()
    else:
        request.user.connected = False
        request.user.save()    
    
    context = {
        'is_connected': request.user.connected,
    }
    return render(request, 'base/whatsapp_session.html', context)

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
            return JsonResponse({'error': 'Failed to retrieve WhatsApp details'}, status=500)
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
        