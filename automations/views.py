from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import hashlib
import hmac
import os
from dotenv import load_dotenv  

load_dotenv()
# Replace with your actual Signature token
SIGNATURE_TOKEN = os.getenv('SIGNATURE_TOKEN')

@csrf_exempt  # Disable CSRF protection for webhook endpoint
@require_POST  # Only allow POST requests
def webhook(request):
    # Get headers
    security_strategy = request.headers.get('X-Salla-Security-Strategy')
    signature = request.headers.get('X-Salla-Signature')
    # Get payload (assuming it's JSON)
    payload = request.body
    

    if security_strategy == "Signature" and signature:
        # Calculate expected HMAC signature
        expected_signature = hmac.new(
            SIGNATURE_TOKEN.encode('utf-8'),
            msg=payload,
            digestmod=hashlib.sha256
        ).hexdigest()

        # Compare the calculated signature with the received signature
        if hmac.compare_digest(expected_signature, signature):
            # Signature is valid
            print("Signature verified successfully")
            print(payload.decode('utf-8'))
            return JsonResponse({"message": "Signature verified successfully"})
        else:
            # Signature is not valid
            print("Signature verification failed")
            return JsonResponse({"message": "Signature verification failed"}, status=403)
    else:
        # Invalid security strategy or missing signature
        print("Invalid security strategy or missing signature header")
        return JsonResponse({"message": "Invalid security strategy or missing signature header"}, status=403)
