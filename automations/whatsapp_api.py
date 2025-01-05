import requests
import base64
import time
from base.models import User, UserStoreLink, MessagesSent, Store
import logging

logger = logging.getLogger(__name__)


def get_session_status(session):
    headers = {'accept': 'application/json', 'Content-Type': 'application/json'}
    status_url = f"http://10.1.0.5:3000/api/sessions/{session}"

    try:
        response = requests.get(status_url, headers=headers)
        response_data = response.json()

        # Check for the presence of the session status
        if response.status_code == 200 and response_data and "status" in response_data:
            return response_data["status"]

        # Handle session not found error (404)
        if response.status_code == 404:
            error_data = response_data if isinstance(response_data, dict) else {}
            if error_data.get("message") == "Session not found":
                print(f"ERROR: Session '{session}' not found. Details: {error_data}")
            return "NOT_FOUND"

        # Handle other non-200 responses
        if response.status_code != 200:
            print(f"Unexpected error. Status: {response.status_code}, Response: {response_data}")
            return None

    except requests.RequestException as e:
        print(f"Network or Request error: {e}")
        return None
    except ValueError:
        print("Invalid JSON response")
        return None


def get_qr_code(session):
    qr_url = f"http://10.1.0.5:3000/api/{session}/auth/qr"
    qr_response = requests.get(qr_url, headers={'accept': 'image/png'})
    if qr_response.status_code in [200, 201]:
        qr_base64 = base64.b64encode(qr_response.content).decode('utf-8')
        return {'success': True, 'qr': qr_base64}
    return {'success': False}

def whatsapp_create_session(user, create=None):
    session = user.session_id
    headers = {'accept': 'application/json', 'Content-Type': 'application/json'}

    start_url = "http://10.1.0.5:3000/api/sessions/start"
    create_url = "http://10.1.0.5:3000/api/sessions"
    data = {
        "name": session,
        "start": True,
        "config": {
            "metadata": {
            "user.id": UserStoreLink.objects.filter(user=user).first().store.store_id,
            },
                "proxy": None,
                "debug": False,
                "noweb": {
                "store": {
                    "enabled": True,
                    "fullSync": False
                }
                },
            "webhooks": [
            {
                "url": "https://risalabot.com/whatsapp",
                "events": [
                "message",
                "session.status"
                ],
            }
            ]
        }
        }

    if create:
        url = create_url
    else:
        url = start_url
    response = requests.post(url, headers=headers, json=data)
    
    if response.status_code in [200, 201]:
        return {'success': True}
    else:
        return {'success': False}
    
    
def whatsapp_details(user):
    session = user.session_id
    headers = {'accept': 'application/json', 'Content-Type': 'application/json'}
    
    # Fetch user details
    url = f"http://10.1.0.5:3000/api/sessions/{session}/me"
    response = requests.get(url, headers=headers)
    
    if response.status_code in [200, 201]:
        response_data = response.json()
        id = response_data['id']
        name = response_data['pushName']
        
    

        # Fetch profile picture
        profile_pic_url = "http://10.1.0.5:3000/api/contacts/profile-picture"
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
    url = f"http://10.1.0.5:3000/api/sessions/logout"
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
    url = "http://10.1.0.5:3000/api/sessions/start"
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
    url = "http://10.1.0.5:3000/api/sessions/stop"
    response = requests.post(url, headers=headers, json=data)
    
    if response.status_code in [200, 201]:
        user.connected = False
        user.save()
        return {'success': True}
    else:
        return {'success': False}


def delete_session(user):
    session = user.session_id
    headers = {'accept': 'application/json', 'Content-Type': 'application/json'}
    # Delete the session
    url = f"http://10.1.0.5:3000/api/sessions/{session}"
    response = requests.delete(url, headers=headers)
    logger.info(f"Deleting session for user: {user.email}")

    
    if response.status_code in [200, 201]:
        user.connected = False
        user.save()
        return {'success': True}
    else:
        return {'success': False}


def send_whatsapp_message(number, msg, session, store):
    url = 'http://10.1.0.5:3000/api/sendText'
    headers = {'accept': 'application/json', 'Content-Type': 'application/json'}
    number = clean_number(number)
    data = {
        'chatId': number,
        "text": msg,
        "session": session
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code in [200, 201]:
            response_data = response.json()
            logger.info(response_data)
            number = number.split('@')[0]
            MessagesSent.objects.create(
                store=store,
                to_number=number,
                message=msg
            )
            return True, "Message sent successfully"

        else:
            return False, "Message failed."
    except requests.exceptions.RequestException as e:
        return False, f"Error occurred when sending message: {e}"

def clean_number(number):
    #remove the + and spaces from the number
    return number.replace('+', '').replace(' ', '')
    