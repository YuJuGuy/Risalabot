# myapp/management/commands/add_existing_customers_to_group.py

from django.core.management.base import BaseCommand
from django.db import transaction
from base.models import Customer, Group

class Command(BaseCommand):
    help = 'Add all existing customers to the "جميع العملاء" group for their respective stores'

    def handle(self, *args, **kwargs):
        # Retrieve all customers
        customers = Customer.objects.all()
        for customer in customers:
            # Ensure the 'جميع العملاء' group exists for the customer's store
            all_customers_group, _ = Group.objects.get_or_create(
                name='جميع العملاء',
                store=customer.store,
                defaults={'group_id': int(f"1111{customer.store.store_id}")}  # Adjust as needed
            )
            
            # Add the customer to the 'جميع العملاء' group if not already a member
            if not customer.customer_groups.filter(id=all_customers_group.id).exists():
                with transaction.atomic():
                    customer.customer_groups.add(all_customers_group)
                    self.stdout.write(
                        f"Added {customer.customer_name} to 'جميع العملاء' group in store {customer.store.store_name}"
                    )
        
        self.stdout.write(self.style.SUCCESS('All existing customers have been added to the "جميع العملاء" group'))
