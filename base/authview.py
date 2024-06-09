from django.shortcuts import redirect
from django.contrib import messages
from django.http import JsonResponse,HttpRequest
import requests
from . forms import CreateUserForm
from . models import User, Store
from dotenv import load_dotenv
import os
import random

load_dotenv()

CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
REDIRECT_URI = os.getenv('REDIRECT_URI')
SCOPE = os.getenv('SCOPE')
SALLA_STORE_INFO_URL = os.getenv('SALLA_STORE_INFO_URL')


def authstore(request):
    # Check if the user is already linked to a store
    user_linked = Store.objects.filter(user=request.user).exists()

    if user_linked:
        # User is already linked, show an error message
        messages.error(request, 'You are already connected to a store.')
        return redirect('dashboard')  # Redirect to the dashboard

    # Proceed with authentication process
    state = str(random.randint(1000000000, 9999999999))    
    auth_url = (
        f"https://accounts.salla.sa/oauth2/auth?client_id={CLIENT_ID}&response_type=code"
        f"&redirect_uri={REDIRECT_URI}&scope={SCOPE}&state={state}"
    )
    
    # Store the linkage status in session data

    return redirect(auth_url)

def callback(request):
    try:
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
            # Extract access token and refresh token from the token response
            access_token = token_response.json().get('access_token')
            refresh_token = token_response.json().get('refresh_token')

            # Fetch store information using the access token
            headers = {'Authorization': f'Bearer {access_token}'}
            store_info_response = requests.get(SALLA_STORE_INFO_URL, headers=headers)
            
            if store_info_response.status_code == 200:
                # Parse store information from the response
                store_info = store_info_response.json()['data']
                store_name = store_info.get('name')
                store_id = store_info.get('id')
                
                # Save store information to the database
                Store.objects.create(
                    user=request.user,
                    store_name=store_name,
                    store_id=store_id,
                    access_token=access_token,
                    refresh_token=refresh_token
                )

                # Redirect to the dashboard
                return redirect('dashboard')
            else:
                # Show error message if failed to fetch store info
                messages.error(request, 'Failed to fetch store information from Salla')
                return redirect('dashboard')
        else:
            # Show error message if failed to receive tokens
            messages.error(request, 'Failed to receive access token from Salla')
            return redirect('dashboard')

    except Exception as e:
        # Show error message if an exception occurs
        messages.error(request, f'An error occurred: {e}')
        return redirect('dashboard')