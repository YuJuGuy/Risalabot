import requests
import base64
import time
from base.models import User


def get_session_status(session):
    
    headers = {'accept': 'application/json', 'Content-Type': 'application/json'}
    status_url = f"http://localhost:3000/api/sessions/{session}"
    response = requests.get(status_url, headers=headers)
    
    # Check if the response is valid and contains JSON data
    try:
        response_data = response.json()
    except ValueError:
        return None

    # Check for the presence of the session status
    if response.status_code == 200 and response_data and "status" in response_data:
        return response_data["status"]
    return None

def get_qr_code(session):
    qr_url = f"http://localhost:3000/api/{session}/auth/qr"
    qr_response = requests.get(qr_url, headers={'accept': 'image/png'})
    if qr_response.status_code in [200, 201]:
        qr_base64 = base64.b64encode(qr_response.content).decode('utf-8')
        return {'success': True, 'qr': qr_base64}
    return {'success': False}

def whatsapp_create_session(user):
    session = user.session_id
    headers = {'accept': 'application/json', 'Content-Type': 'application/json'}

    while True:
        # Check if session already exists and its status
        status = get_session_status(session)
        if status == "WORKING":
            user.connected = True
            user.save()
            return {'success': True}
        elif status == "SCAN_QR_CODE":
            return get_qr_code(session)
        elif status == "STARTING":
            # Wait for session to start
            time.sleep(3)
            continue
        elif status == "FAILED":
            return {'success': False}
        else:
            break

    # No session exists, proceed to create a new session
    print("Creating a new session")
    url = "http://localhost:3000/api/sessions/start"
    data = {"name": session}
    response = requests.post(url, headers=headers, json=data)
    
    if response.status_code in [200, 201]:
        # Wait for the session to start and fetch its status again
        time.sleep(3)
        return whatsapp_create_session(user)
    else:
        return {'success': False}
    
    
def whatsapp_details(user):
    session = user.session_id
    headers = {'accept': 'application/json', 'Content-Type': 'application/json'}
    
    # Fetch user details
    url = f"http://localhost:3000/api/sessions/{session}/me"
    response = requests.get(url, headers=headers)
    
    if response.status_code in [200, 201]:
        response_data = response.json()
        id = response_data['id']
        name = response_data['pushName']
        
        # Fetch about info
        about_url = f"http://localhost:3000/api/contacts/about"
        about_params = {"contactId": id, "session": session}
        about_response = requests.get(about_url, headers=headers, params=about_params)
        
        if about_response.status_code in [200, 201]:
            about_data = about_response.json()
            about = about_data.get('about')
        else:
            about = None  # or handle the error accordingly

        # Fetch profile picture
        profile_pic_url = "http://localhost:3000/api/contacts/profile-picture"
        profile_pic_params = {"contactId": id, "session": session}
        profile_picture_response = requests.get(profile_pic_url, headers=headers, params=profile_pic_params)
        
        if profile_picture_response.status_code in [200, 201]:
            profile_pic_data = profile_picture_response.json()
            profile_picture = profile_pic_data.get('profilePictureURL')
        else:
            profile_picture = None  # or handle the error accordingly

        return {
            'id': id,
            'name': name,
            'about': about,
            'profile_picture': profile_picture,
        }
    else:
        user.connected = False
        user.save()
        return None  # or handle the error accordingly
       
       
       
def logout_user(user):
    session = user.session_id
    headers = {'accept': 'application/json', 'Content-Type': 'application/json'}
    data = {"name": session}
    # Logout user
    url = f"http://localhost:3000/api/sessions/logout"
    response = requests.post(url, headers=headers, json=data)
    
    if response.status_code in [200, 201]:
        return {'success': True}
    else:
        return {'success': False}
    
    
def start_session(user):
    session = user.session_id
    headers = {'accept': 'application/json', 'Content-Type': 'application/json'}
    data = {"name": session}
    # Start the session
    url = "http://localhost:3000/api/sessions/start"
    response = requests.post(url, headers=headers, json=data)
    
    if response.status_code in [200, 201]:
        return {'success': True}
    else:
        return {'success': False}
    
def stop_session(user):
    session = user.session_id
    headers = {'accept': 'application/json', 'Content-Type': 'application/json'}
    data = {
        "logout": True,
        "name": session
    }
    
    # Stop the session
    url = "http://localhost:3000/api/sessions/stop"
    response = requests.post(url, headers=headers, json=data)
    
    if response.status_code in [200, 201]:
        return {'success': True}
    else:
        return {'success': False}