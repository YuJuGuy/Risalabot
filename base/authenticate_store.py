from django.shortcuts import redirect
from django.contrib import messages
from django.http import JsonResponse,HttpRequest
from django.contrib.auth.decorators import login_required
import requests
from . models import UserStoreLink, Store, User
import os
import random
from django.utils.crypto import get_random_string
from django.contrib.auth import login
from django.utils import timezone



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
        code = request.GET.get('code')
        if not code:
            return JsonResponse({'error': 'No authorization code provided'}, status=400)
        
        access_token, refresh_token = get_tokens(code)
        if not access_token:
            messages.error(request, 'فشل الحصول على التوكن')
            return redirect('dashboard')

        store_info = fetch_store_info(access_token)
        if not store_info:
            messages.error(request, 'فشل الحصول على معلومات المتجر من ساللا')
            return redirect('dashboard')
        
        store_name, store_id, store_email = store_info.get('name'), store_info.get('id'), store_info.get('email')
        
        # Check if the user is authenticated
        user = authenticate_or_create_user(request, store_email,store_id) if not request.user.is_authenticated else request.user
        if not user:
            return redirect('dashboard')
        
        is_new_connection = handle_store_connection(request, user, store_id, store_name, access_token, refresh_token)
        if is_new_connection:
            messages.success(request, 'تم الاتصال بالمتجر بنجاح.')

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

    if response.status_code == 200:
        return response.json().get('data')
    return None


def authenticate_or_create_user(request, store_email,store_id):
    store_check = UserStoreLink.objects.filter(store__store_id=str(store_id)).first()
    if store_check:
        messages.error(request, 'المتجر مرتبط بمستخدم آخر بالفعل.')
        return None
    
    if not store_email:
        messages.error(request, 'المتجر لا يملك عنوان بريد الكتروني.')
        return None

    user, created = User.objects.get_or_create(email=store_email, defaults={
        'username': store_email,
        'session_id': generate_unique_session_id()
    })

    if created:
        user.set_password(get_random_string(length=32))
        user.save()
        login(request, user)

    return user    


def handle_store_connection(request, user, store_id, store_name, access_token, refresh_token):
    user_store_link = UserStoreLink.objects.filter(user=user).first()
    if user_store_link:
        existing_store_id = str(user_store_link.store.store_id).strip()
        if existing_store_id == str(store_id).strip():
            update_store_tokens(user_store_link.store, access_token, refresh_token)
            messages.success(request, 'تم تحديث قاعدة البيانات بنجاح.')
            return False
        else:
            messages.error(request, 'يرجى الغاء الاتصال بالمتجر القديم قبل الاتصال بالمتجر الجديد.')
            return False

    store, created = Store.objects.get_or_create(
        store_id=store_id,
        defaults={
            'store_name': store_name,
            'access_token': access_token,
            'refresh_token': refresh_token
        }
    )

    if not created:
        update_store_tokens(store, access_token, refresh_token)

    if UserStoreLink.objects.filter(store=store).exists():
        messages.error(request, 'المتجر مرتبط بمستخدم آخر بالفعل.')
        return False

    UserStoreLink.objects.create(user=user, store=store)
    return True


def update_store_tokens(store, access_token, refresh_token):
    store.access_token = access_token
    store.refresh_token = refresh_token
    store.token_valid = True
    store.token_refresh_date = timezone.now()

    store.save()

    
    
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
        messages.success(request, 'تم الغاء الاتصال بالمتجر بنجاح.')
    except UserStoreLink.DoesNotExist:
        messages.error(request, 'انت غير مرتبط بالمتجر المطلوب.')
    except Store.DoesNotExist:
        messages.error(request, 'المتجر غير موجود.')

    return redirect('dashboard')