import requests
from .models import UserStoreLink

def customer_list(user):
    store = UserStoreLink.objects.get(user=user).store
    access_token = store.access_token
    url = "https://api.salla.dev/admin/v2/customers/groups"

    headers = {
        'User-Agent': 'Apidog/1.0.0 (https://apidog.com)',
        'Authorization': f'Bearer {access_token}'
    }

    response = requests.get(url, headers=headers)
    response_data = response.json()

    return response_data if response.status_code == 200 else {'success': False, 'data': []}


def customers(user):
    store = UserStoreLink.objects.get(user=user).store
    access_token = store.access_token
    url = "https://api.salla.dev/admin/v2/customers"

    headers = {
        'User-Agent': 'Apidog/1.0.0 (https://apidog.com)',
        'Authorization': f'Bearer {access_token}'
    }

    response = requests.get(url, headers=headers)
    response_data = response.json()

    return response_data if response.status_code == 200 else {'success': False, 'data': []}