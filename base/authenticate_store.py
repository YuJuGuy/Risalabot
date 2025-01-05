from base.Utils.data_utils import sync_data
from django.shortcuts import redirect
from django.contrib import messages
from django.http import JsonResponse,HttpRequest
from django.contrib.auth.decorators import login_required
from automations.whatsapp_api import stop_session
import requests
from . models import UserStoreLink, Store, User
import os
import random
from django.utils.crypto import get_random_string
from django.contrib.auth import login
from django.utils import timezone
import logging 

logger = logging.getLogger(__name__)



CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
REDIRECT_URI = os.getenv('REDIRECT_URI')
SCOPE = os.getenv('SCOPE')
SALLA_STORE_INFO_URL = os.getenv('SALLA_STORE_INFO_URL')


def generate_unique_session_id():
    """Generate a unique session_id for the user."""
    while True:
        session_id = get_random_string(length=32)
        if not User.objects.filter(session_id=session_id).exists():
            return session_id

def authstore(request):

    state = str(random.randint(1000000000, 9999999999))

    auth_url = (
        f"https://accounts.salla.sa/oauth2/auth?client_id={CLIENT_ID}&response_type=code"
        f"&redirect_uri={REDIRECT_URI}&scope={SCOPE}&state={state}"
    )
    return redirect(auth_url)


def callback(request):
    try:
        logger.info("DEBUG: Starting callback function")
        logger.info(f"DEBUG: User authenticated status: {request.user.is_authenticated}")
        
        code = request.GET.get('code')
        if not code:
            logger.info("DEBUG: No code provided")
            return JsonResponse({'error': 'No authorization code provided'}, status=400)
        
        logger.info(f"DEBUG: Got code: {code[:10]}...")  # Only logger.info first 10 chars for security
        
        access_token, refresh_token = get_tokens(code)
        if not access_token:
            logger.info("DEBUG: Failed to get access token")
            messages.error(request, 'فشل الحصول على التوكن')
            return redirect('dashboard')

        logger.info("DEBUG: Successfully got access token")
        
        store_info = fetch_store_info(access_token)
        if not store_info:
            logger.info("DEBUG: Failed to fetch store info")
            messages.error(request, 'فشل الحصول على معلومات المتجر من سلة')
            return redirect('dashboard')
        
        logger.info(f"DEBUG: Store info retrieved: {store_info}")
        
        store_name = store_info.get('name')
        store_id = store_info.get('id')
        store_email = store_info.get('email')
        store_domain = store_info.get('domain')
        
        logger.info(f"DEBUG: Extracted store details - Name: {store_name}, ID: {store_id}, Email: {store_email}")
        
        # Check if store is already connected
        if UserStoreLink.objects.filter(store__store_id=str(store_id)).exists():
            logger.info(f"DEBUG: Store {store_id} already connected to another user")
            messages.error(request, 'المتجر مرتبط بمستخدم آخر بالفعل.')
            return redirect('dashboard')

        # Flow 1: Connecting store without having a user
        if not request.user.is_authenticated:
            logger.info("DEBUG: Starting Flow 1 - New user creation")
            user, created = authenticate_or_create_user(request, store_email, store_id)
            logger.info(f"DEBUG: User creation result - User: {user}, Created: {created}")
            
            if not user:
                logger.info("DEBUG: Failed to create/authenticate user")
                return redirect('dashboard')
            
            is_new_connection = handle_store_connection(request, user, store_id, store_name, store_domain, access_token, refresh_token)
            logger.info(f"DEBUG: Store connection result: {is_new_connection}")
            
            if is_new_connection:
                logger.info("DEBUG: New connection successful, redirecting to account")
                messages.success(request, 'تم انشاء حساب جديد والاتصال بالمتجر بنجاح. يرجى تغيير كلمة المرور.')
                return redirect('account')

                # Flow 2: New user connects store (already authenticated)
        elif not UserStoreLink.objects.filter(user=request.user).exists():
            is_new_connection = handle_store_connection(request, request.user, store_id, store_name, store_domain, access_token, refresh_token)
            if is_new_connection:
                messages.success(request, 'تم الاتصال بالمتجر بنجاح.')
                return redirect('dashboard')

        # Flow 3: Existing user connects store
        else:
            is_new_connection = handle_store_connection(request, request.user, store_id, store_name, store_domain, access_token, refresh_token)
            if is_new_connection:
                messages.success(request, 'تم الاتصال بالمتجر بنجاح.')
                return redirect('dashboard')

        return redirect('dashboard')

    except Exception as e:
        messages.error(request, f'فشل الاتصال بالمتجر: {e}')
        return redirect('dashboard')




def get_tokens(code):
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
        token_json = token_response.json()
        return token_json.get('access_token'), token_json.get('refresh_token')
    return None, None


def fetch_store_info(access_token):
    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.get(SALLA_STORE_INFO_URL, headers=headers)
    logger.info(response.json().get('data'))
    if response.status_code == 200:
        return response.json().get('data')
    return None


def authenticate_or_create_user(request, store_email, store_id):
    logger.info(f"DEBUG: Starting authenticate_or_create_user")
    logger.info(f"DEBUG: Store email: {store_email}")
    logger.info(f"DEBUG: Store ID: {store_id}")
    
    if not store_email:
        logger.info("DEBUG: No store email provided")
        messages.error(request, 'المتجر لا يملك عنوان بريد الكتروني.')
        return None, False

    try:
        # Check if user already exists
        existing_user = User.objects.filter(email=store_email).first()
        logger.info(f"DEBUG: Existing user check result: {existing_user}")

        if existing_user:
            logger.info("DEBUG: Found existing user, attempting login")
            login(request, existing_user)
            logger.info(f"DEBUG: Login status after existing user login: {request.user.is_authenticated}")
            return existing_user, False
        
        logger.info("DEBUG: Creating new user")
        # Create new user
        new_user = User.objects.create(
            email=store_email,
            username=store_email,
            session_id=generate_unique_session_id()
        )
        logger.info(f"DEBUG: New user created with ID: {new_user.id}")
        
        # Set password and login
        random_password = get_random_string(length=32)
        new_user.set_password(random_password)
        new_user.save()
        logger.info("DEBUG: Password set for new user")
        
        # Attempt login
        logger.info("DEBUG: Attempting to login new user")
        login(request, new_user)
        logger.info(f"DEBUG: Login status after new user login: {request.user.is_authenticated}")
        
        return new_user, True
        
    except Exception as e:
        logger.info(f"DEBUG: Exception in authenticate_or_create_user: {str(e)}")
        logger.info(f"DEBUG: Exception type: {type(e)}")
        import traceback
        logger.info(f"DEBUG: Traceback: {traceback.format_exc()}")
        return None, False

def handle_store_connection(request, user, store_id, store_name, store_domain, access_token, refresh_token):
    logger.info(f"DEBUG: Starting handle_store_connection for user: {user.email}, store: {store_id}")
    
    # First check if this user already has a store connection
    user_store_link = UserStoreLink.objects.filter(user=user).first()
    if user_store_link:
        logger.info(f"DEBUG: Found existing store link for user")
        existing_store_id = str(user_store_link.store.store_id).strip()
        if existing_store_id == str(store_id).strip():
            logger.info("DEBUG: Updating existing store tokens")
            update_store_tokens(user_store_link.store, access_token, refresh_token)
            messages.success(request, 'تم تحديث قاعدة البيانات بنجاح.')
            return False
        else:
            logger.info("DEBUG: User already has different store connected")
            messages.error(request, 'يرجى الغاء الاتصال بالمتجر القديم قبل الاتصال بالمتجر الجديد.')
            return False

    try:
        # Create or get the store
        store, created = Store.objects.get_or_create(
            store_id=store_id,
            defaults={
                'store_name': store_name,
                'store_domain': store_domain,
                'access_token': access_token,
                'refresh_token': refresh_token
            }
        )
        logger.info(f"DEBUG: Store created: {created}")

        if not created:
            logger.info("DEBUG: Updating existing store")
            update_store_tokens(store, access_token, refresh_token)

        # Create the user-store link
        UserStoreLink.objects.create(user=user, store=store)
        logger.info("DEBUG: Created user-store link")
        return True
        
    except Exception as e:
        logger.info(f"DEBUG: Exception in handle_store_connection: {str(e)}")
        return False


def update_store_tokens(store, access_token, refresh_token):
    store.access_token = access_token
    store.refresh_token = refresh_token
    store.token_valid = True
    store.token_refresh_date = timezone.now()
    store.save()
    

    
    
@login_required(login_url='login')
def unlinkstore(request):
    try:
        # Ensure the user is linked to the store
        link = UserStoreLink.objects.get(user=request.user)
        store_id = link.store.store_id
        user = link.user
        # Delete the user-store link
        stop_session(user)

        link.delete()

        # Get the store and invalidate its tokens
        store = Store.objects.get(store_id=store_id)
        store.access_token = None
        store.refresh_token = None
        store.token_valid = False
        store.save()


        # json respnse with redirect link
        return JsonResponse({'success': True, 'type': 'success', 'message': 'تم الغاء الاتصال بالمتجر بنجاح.', 'redirect_url': '/dashboard/'}, status=200)
    except UserStoreLink.DoesNotExist:
        return JsonResponse({'success': False, 'type': 'error', 'message': 'لم يتم العثور على متجر للمستخدم.'}, status=400)
    except Store.DoesNotExist:
        return JsonResponse({'success': False, 'type': 'error', 'message': 'لم يتم العثور على متجر.'}, status=400)

    except Exception as e:
        return JsonResponse({'success': False, 'type': 'error', 'message': str(e)}, status=500)
        
    return None


    