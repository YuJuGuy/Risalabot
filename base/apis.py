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
    
    customers = []
    for customer in response_data.get('data', []):
        customer_id = customer.get('id')
        first_name = customer.get('first_name', "No first name")
        last_name = customer.get('last_name', "No last name")
        email = customer.get('email', "No email")
        phone = f"{customer.get('mobile_code', '')}{customer.get('mobile', 'No phone')}"
        updated_at = customer.get('updated_at', "No update time")
        groups = customer.get('groups', [])
        
        customers.append({
            'customer_id': customer_id,
            'name': f"{first_name} {last_name}",
            'email': email,
            'phone': phone,
            'updated_at': updated_at,
            'groups': groups
        })
    
    return customers if response.status_code == 200 else []
    
