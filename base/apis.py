import requests
from datetime import datetime
from .models import UserStoreLink



def get_customer_data(user):
    store = UserStoreLink.objects.get(user=user).store
    access_token = store.access_token
    
    headers = {
        'User-Agent': 'Apidog/1.0.0 (https://apidog.com)',
        'Authorization': f'Bearer {access_token}'
    }
    
    # Fetch customers
    customers_url = "https://api.salla.dev/admin/v2/customers"
    customers_response = requests.get(customers_url, headers=headers)
    customers_data = customers_response.json()

    # Fetch customer groups
    groups_url = "https://api.salla.dev/admin/v2/customers/groups"
    groups_response = requests.get(groups_url, headers=headers)
    groups_data = groups_response.json()
    
    # Check for errors in API responses
    if customers_response.status_code != 200 or groups_response.status_code != 200:
        return {'success': False, 'data': []}
    
    customers = []
    group_counts = {}
    group_id_to_name = {}
    
    for group in groups_data.get('data', []):
        group_id = group['id']
        group_name = group['name']
        group_counts[group_id] = 0
        group_id_to_name[group_id] = group_name
    
    for customer in customers_data.get('data', []):
        customer_id = customer.get('id')
        first_name = customer.get('first_name', "No first name")
        last_name = customer.get('last_name', "No last name")
        email = customer.get('email', "No email")
        phone = f"{customer.get('mobile_code', '')}{customer.get('mobile', 'No phone')}"
        
        group_ids = customer.get('groups', [])
        customer_groups = []
        
        for group_id in group_ids:
            if group_id in group_counts:
                group_counts[group_id] += 1
                customer_groups.append(group_id_to_name[group_id])
        
        updated_at = customer.get('updated_at', "No update time")
        updated_at = datetime.strptime(updated_at['date'], "%Y-%m-%d %H:%M:%S.%f").strftime("%Y-%m-%d %H:%M:%S")
        
        location = customer.get('country', '')
        if customer.get('city') != "":
            location += f", {customer.get('city')}"
        
        customers.append({
            'customer_id': customer_id,
            'name': f"{first_name} {last_name}",
            'email': email,
            'phone': phone,
            'updated_at': updated_at,
            'location': location,
            'groups': customer_groups
        })
    
    return {'success': True, 'customers': customers, 'group_counts': group_counts, 'group_id_to_name': group_id_to_name}


def create_customer_group(user, group_name):
    store = UserStoreLink.objects.get(user=user).store
    access_token = store.access_token
    
    headers = {
        'User-Agent': 'Apidog/1.0.0 (https://apidog.com)',
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    data = {
        'name': group_name
    }
    
    groups_url = "https://api.salla.dev/admin/v2/customers/groups"
    response = requests.post(groups_url, headers=headers, json=data)
    
    return response.json()


def delete_customer_group(user,group_id):
    store = UserStoreLink.objects.get(user=user).store
    access_token = store.access_token
    
    headers = {
        'User-Agent': 'Apidog/1.0.0 (https://apidog.com)',
        'Authorization': f'Bearer {access_token}'
    }
    
    groups_url = f"https://api.salla.dev/admin/v2/customers/groups/{group_id}"
    response = requests.delete(groups_url, headers=headers)
    
    return response.json()
