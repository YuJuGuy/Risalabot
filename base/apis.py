import requests
from datetime import datetime
from .models import UserStoreLink
import base64
import time



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
            customers.append(customer_number)
            
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



def get_session_status(session, headers):
    status_url = f"http://localhost:3000/api/sessions/{session}"
    response = requests.get(status_url, headers=headers)
    
    # Check if the response is valid and contains JSON data
    try:
        response_data = response.json()
    except ValueError:
        return None

    # Check for the presence of the session status
    if response.status_code == 200 and "status" in response_data:
        return response_data["status"]
    return None

def get_qr_code(session):
    qr_url = f"http://localhost:3000/api/{session}/auth/qr"
    qr_response = requests.get(qr_url, headers={'accept': 'image/png'})
    if qr_response.status_code in [200, 201]:
        qr_base64 = base64.b64encode(qr_response.content).decode('utf-8')
        return {'success': True, 'message': 'Session created successfully', 'qr': qr_base64}
    return {'success': False, 'message': 'Failed to retrieve QR code'}

def whatsapp_create_session(user):
    session = user.session_id
    headers = {'accept': 'application/json', 'Content-Type': 'application/json'}

    # Check if session already exists and its status
    status = get_session_status(session, headers)
    if status == "WORKING":
        return {'success': True, 'message': 'Session is already working'}
    elif status == "SCAN_QR_CODE":
        return get_qr_code(session)
    elif status == "STARTING":
        # Wait for session to start
        while status == "STARTING":
            time.sleep(3)
            status = get_session_status(session, headers)
        if status == "SCAN_QR_CODE":
            return get_qr_code(session)
        elif status == "WORKING":
            return {'success': True, 'message': 'Session is already working'}
        elif status == "FAILED":
            return {'success': False, 'message': 'Session failed to start'}
    
    elif status is None:
        # No session exists, proceed to create a new session
        url = "http://localhost:3000/api/sessions/start"
        data = {"name": session}
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code in [200, 201]:
            while True:
                status = get_session_status(session, headers)
                if status == "SCAN_QR_CODE":
                    return get_qr_code(session)
                elif status == "STARTING":
                    time.sleep(3)
                elif status == "WORKING":
                    return {'success': True, 'message': 'Session is already working'}
                else:
                    return {'success': False, 'message': f'Session status: {status}'}
        elif response.status_code == 422:
            return {'success': False, 'message': 'Failed to create session: Unprocessable Entity'}
        else:
            return {'success': False, 'message': 'Failed to create session'}
    else:
        return {'success': False, 'message': f'Unexpected session status: {status}'}