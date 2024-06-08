from django.shortcuts import redirect
from django.http import JsonResponse,HttpRequest
import requests
from . forms import CreateUserForm
from . models import User
from dotenv import load_dotenv
import os
import random

load_dotenv()

CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
REDIRECT_URI = os.getenv('REDIRECT_URI')
SCOPE = os.getenv('SCOPE')
SALLA_STORE_INFO_URL = os.getenv('SALLA_STORE_INFO_URL')

def authstore(request: HttpRequest):
    state = str(random.randint(1000000000, 9999999999))
    request.session['oauth_state'] = state
    
    auth_url = (
        f"https://accounts.salla.sa/oauth2/auth?client_id={CLIENT_ID}&response_type=code"
        f"&redirect_uri={REDIRECT_URI}&scope={SCOPE}&state={state}"
    )
    return redirect(auth_url)

def callback(request):
    try:
        # Validate state parameter to prevent CSRF attacks
        state = request.GET.get('state')
        if state != request.session.pop('oauth_state', None):
            return JsonResponse({'error': 'Invalid state parameter'}, status=400)
        
        # Get authorization code from the request
        code = request.GET.get('code')
        if not code:
            return JsonResponse({'error': 'No authorization code provided'}, status=400)
        
        # Exchange authorization code for access token
        token_data = {
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': REDIRECT_URI,
            'scope': SCOPE
        }
        token_response = requests.post('https://accounts.salla.sa/oauth2/token', data=token_data)
        
        if token_response.status_code == 200:
            access_token = token_response.json().get('access_token')
            refresh_token = token_response.json().get('refresh_token')

            print('Access Token:' + access_token)
            print('Refresh Token:' + refresh_token)
            
            headers = {'Authorization': f'Bearer {access_token}'}
            
            # Fetch store information
            store_info_response = requests.get(SALLA_STORE_INFO_URL, headers=headers)
            
            if store_info_response.status_code == 200:
                store_info = store_info_response.json()
                
                # Print or jsonify store info
                print(store_info)
                return redirect('dashboard')
        
        return JsonResponse({'error': 'Failed to receive token or fetch store info'}, status=400)
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)