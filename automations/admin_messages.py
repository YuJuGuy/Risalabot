import requests
import base64
import time
import logging

logger = logging.getLogger(__name__)




def send_working_message(number, case):
    url = 'http://10.1.0.5:3000/api/sendText'
    headers = {'accept': 'application/json', 'Content-Type': 'application/json'}
    working_message = "تم ربط الحساب بنجاح"
    disconnect_message = "تم قطع الاتصال بالحساب"

    message = working_message if case == "working" else disconnect_message

    data = {
        'chatId': number,
        "text": message,
        "session": 'default'
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code in [200, 201]:
            return True, "Message sent successfully."
        else:
            logger.error(f"Message sending failed. Status: {response.status_code}, Response: {response.text}")
            return False, f"Failed to send message. Status code: {response.status_code}"
    except requests.exceptions.RequestException as e:
        logger.error(f"Error occurred when sending message: {e}")
        return False, f"Error occurred when sending message: {e}"
