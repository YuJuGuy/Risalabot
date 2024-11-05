import requests
from datetime import datetime
from .models import UserStoreLink
import base64
import time


def get_customer_count(user):
    try:
        store = UserStoreLink.objects.get(user=user).store
        access_token = store.access_token
        
        headers = {
            'Authorization': f'Bearer {access_token}'
        }
        
        customers_url = "https://api.salla.dev/admin/v2/customers"
        response = requests.get(customers_url, headers=headers)
        response.raise_for_status()
        customers_data = response.json()
        
        return {
            'success': True,
            'customer_count': len(customers_data.get('data', []))
        }
    except UserStoreLink.DoesNotExist:
        return {
            'success': False,
            'message': 'UserStoreLink does not exist for the given user.'
        }
    except requests.RequestException as e:
        return {
            'success': False,
            'message': str(e)
        }
    except Exception as e:
        return {
            'success': False,
            'message': str(e)
        }

def group_campaign(user):
    store = UserStoreLink.objects.get(user=user).store
    access_token = store.access_token
    
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    
    group_url = "https://api.salla.dev/admin/v2/customers/groups"
    group_response = requests.get(group_url, headers=headers)
    group_data = group_response.json()
    
    return group_data

def get_customers_from_group(user, group_id):
    store = UserStoreLink.objects.get(user=user).store
    access_token = store.access_token
    
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    
    customers_url = f"https://api.salla.dev/admin/v2/customers/"
    
    response = requests.get(customers_url, headers=headers)
    customers_data = response.json()
    customers = []
    
    for customer in customers_data.get('data', []):
        customer_groups = customer.get('groups', [])
        
        if int(group_id) in [int(group) for group in customer_groups]:
            customer_number = str(customer.get('mobile_code')) + str(customer.get('mobile'))
            customer_full_name = f"{customer.get('first_name')} {customer.get('last_name')}"
            customer_first_name = customer.get('first_name', '')
            customer_email = customer.get('email', '')
            customer_country = customer.get('country', '')
            customers.append({
                'customer_number': customer_number,
                'customer_full_name': customer_full_name,
                'customer_first_name': customer_first_name,
                'customer_country': customer_country,
                'customer_email': customer_email
            })
            
    return customers

def get_customer_data(user):
    store = UserStoreLink.objects.get(user=user).store
    access_token = store.access_token
    
    headers = {
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
    
    # Map group_id to name for each group from API
    for group in groups_data.get('data', []):
        group_id = int(group['id'])  # Ensure group_id is an integer
        group_name = group['name']
        group_counts[group_id] = 0
        group_id_to_name[group_id] = group_name
    
    # Process each customer
    for customer in customers_data.get('data', []):
        customer_id = customer.get('id')
        first_name = customer.get('first_name', "No first name")
        last_name = customer.get('last_name', "No last name")
        email = customer.get('email', "No email")
        phone = f"{customer.get('mobile_code', '')}{customer.get('mobile', 'No phone')}"
        
        # Use group IDs as integers, not names
        group_ids = [int(group_id) for group_id in customer.get('groups', []) if group_id in group_id_to_name]
        
        # Update counts for each group_id
        for group_id in group_ids:
            group_counts[group_id] += 1
        
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
            'groups': group_ids  # Pass group IDs as integers
        })
        
    
    return {'success': True, 'customers': customers, 'group_counts': group_counts, 'group_id_to_name': group_id_to_name}



def create_customer_group(user, group_name, condtion=None):
    store = UserStoreLink.objects.get(user=user).store
    access_token = store.access_token
    
    headers = {
        'User-Agent': 'Apidog/1.0.0 (https://apidog.com)',
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    if condtion:
        data = {
            'name': group_name,
            'conditions': condtion
        }
    else:
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



