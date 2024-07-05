from celery import shared_task 

from django.core.mail import send_mail

from time import sleep

@shared_task
def sleepy(duration):
    sleep(duration)
    return None

@shared_task(acks_late=True)
def send_email_task(numbers, msg):
    i = 0
    for number in numbers:
        if i <= 1:
            print(f"Sending email to {number} with message: {msg}")
            i += 1
        else:
            print(f"Failed to send email to {number} with message: {msg}")
            
    return None