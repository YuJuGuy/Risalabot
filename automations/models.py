from django.db import models
from django.utils import timezone

# Create your models here.

from base.models import Store


class MonthlyPayments(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    date = models.DateTimeField(auto_now_add=True)
    amount = models.CharField(max_length=255)
    subscribtion = models.CharField(max_length=255)
    reference_number = models.CharField(max_length=100, unique=True)



class MonthlyInstallations(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    date = models.DateTimeField(auto_now_add=True)
    reference_number = models.CharField(max_length=100, unique=True)

    def save(self, *args, **kwargs):
    # Get the current month and year
        current_date = timezone.now()
        current_month = current_date.month
        current_year = current_date.year
        
        # Check if an installation already exists for this store in the current month
        existing_installation = MonthlyInstallations.objects.filter(
            store=self.store,
            date__month=current_month,
            date__year=current_year
        ).exists()
        
        # If no installation exists for this month, save the new one
        if not existing_installation:
            super().save(*args, **kwargs)

    


class AppTrial(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    date = models.DateTimeField(auto_now_add=True)
    reference_number = models.CharField(max_length=100, unique=True)
