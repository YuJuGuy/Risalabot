from celery import shared_task 

from django.core.mail import send_mail

from time import sleep

@shared_task
def sleepy(duration):
    sleep(duration)
    return None

@shared_task(acks_late=True)
def send_email_task():
    sleep(20)
    print('Mail Sent')

    return None