from django.shortcuts import redirect
from django.contrib import messages
from django.http import JsonResponse,HttpRequest
from django.contrib.auth.decorators import login_required
import requests
from . models import UserStoreLink, Store, UserEvent, User
from dotenv import load_dotenv
import os
import random
from django.utils.crypto import get_random_string
from django.contrib.auth import login

load_dotenv()

CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
REDIRECT_URI = os.getenv('REDIRECT_URI')
SCOPE = os.getenv('SCOPE')
SALLA_STORE_INFO_URL = os.getenv('SALLA_STORE_INFO_URL')


def authstore(request):
    # If user is authenticated, check if they are already linked to a store
    if request.user.is_authenticated:
        user_linked = UserStoreLink.objects.filter(user=request.user).exists()

        if user_linked:
            # User is already linked, show an error message
            messages.error(request, 'You are already connected to a store.')
            return redirect('dashboard')  # Redirect to the dashboard

    # Proceed with authentication process
    state = str(random.randint(1000000000, 9999999999))

    # Print debug information for scope
    print(f"SCOPE: {SCOPE}")

    auth_url = (
        f"https://accounts.salla.sa/oauth2/auth?client_id={CLIENT_ID}&response_type=code"
        f"&redirect_uri={REDIRECT_URI}&scope={SCOPE}&state={state}"
    )

    # Print debug information for URL
    return redirect(auth_url)

def generate_unique_session_id():
    """Generate a unique session_id for the user."""
    while True:
        session_id = get_random_string(length=32)
        if not User.objects.filter(session_id=session_id).exists():
            return session_id

def callback(request):
    try:
        code = request.GET.get('code')
        if not code:
            return JsonResponse({'error': 'No authorization code provided'}, status=400)

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

            headers = {'Authorization': f'Bearer {access_token}'}
            store_info_response = requests.get(SALLA_STORE_INFO_URL, headers=headers)

            if store_info_response.status_code == 200:
                store_info = store_info_response.json()['data']
                store_name = store_info.get('name')
                store_id = store_info.get('id')
                # check if the store has an email and not null
                store_email = store_info.get('email')
                
                
                # Check if the user is authenticated
                if not request.user.is_authenticated:
                    # Generate a random username and session ID
                    print("Generating a new session ID")
                    session_id = generate_unique_session_id()
                    
                    
                    # Check if the store has an email and not null
                    
                    if not store_email or store_email == '':
                        messages.error(request, 'The store does not have an email address.')
                        return redirect('dashboard')
                    # Create a new user
                    user, created = User.objects.get_or_create(email=store_email, defaults={
                        'username': store_email,
                        'session_id': session_id
                    })

                    if created:
                        # Automatically log in the new user
                        user.set_password(get_random_string(length=32))  # Ensure password is hashed
                        user.save()
                        login(request, user)  # Log in the new user
                else:
                    user = request.user

                store, created = Store.objects.get_or_create(
                    store_id=store_id,
                    defaults={
                        'store_name': store_name,
                        'access_token': access_token,
                        'refresh_token': refresh_token
                    }
                )

                if not created:
                    store.access_token = access_token
                    store.refresh_token = refresh_token
                    store.token_valid = True
                    store.save()

                if UserStoreLink.objects.filter(store=store).exists():
                    messages.error(request, 'This store is already connected to another user.')
                    return redirect('dashboard')
                
                if UserStoreLink.objects.filter(user=user).exists():
                    messages.error(request, 'You are already connected to a store.')
                    return redirect('dashboard')  # Redirect to the dashboard

                UserStoreLink.objects.create(user=user, store=store)
                return redirect('dashboard')
            else:
                messages.error(request, 'Failed to fetch store information from Salla')
                return redirect('dashboard')
        else:
            messages.error(request, 'Failed to receive access token from Salla')
            return redirect('dashboard')

    except Exception as e:
        messages.error(request, f'An error occurred: {e}')
        return redirect('dashboard')
    
    
@login_required(login_url='login')
def unlinkstore(request, store_id):
    try:
        # Ensure the user is linked to the store
        link = UserStoreLink.objects.get(user=request.user, store__store_id=store_id)
        # Delete the user-store link
        link.delete()

        # Get the store and invalidate its tokens
        store = Store.objects.get(store_id=store_id)
        store.access_token = None
        store.refresh_token = None
        store.token_valid = False
        store.save()

        # Removed code that deletes the UserEvent entry
        messages.success(request, 'You have been disconnected from the store.')
    except UserStoreLink.DoesNotExist:
        messages.error(request, 'You are not connected to this store.')
    except Store.DoesNotExist:
        messages.error(request, 'Store not found.')

    return redirect('dashboard')