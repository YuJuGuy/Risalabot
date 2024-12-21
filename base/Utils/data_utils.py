from django.http import JsonResponse
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from base.models import Notification, UserStoreLink, Store, Customer, Group
import logging
from base.apis import get_customer_data
from django.db import transaction

logger = logging.getLogger(__name__)


@login_required(login_url='login')
def clear_notifications(request):
    try:
        user_store_link = UserStoreLink.objects.get(user=request.user)
        store = user_store_link.store
        Notification.objects.filter(store=store).delete()
        return JsonResponse({'success': True, 'type': 'success', 'message': 'تم حذف الاشعارات بنجاح.'}, status=200)
    except UserStoreLink.DoesNotExist:
        return JsonResponse({'success': False, 'type': 'error', 'message': 'لم يتم العثور على متجر للمستخدم'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'type': 'error', 'message': str(e)}, status=500)



@login_required(login_url='login')
@transaction.atomic
def sync_data(request):
    try:
        # Fetch the latest customer data from the API
        customer_data = get_customer_data(request.user)
        if not customer_data.get('success', False):
            logger.error("Failed to fetch customer data from API.")
            return JsonResponse({'error': 'فشل في جلب بيانات العملاء من واجهة برمجة التطبيقات'}, status=500)

        # Get the store associated with the logged-in user
        store = Store.objects.get(userstorelink__user=request.user)

        # Clear out existing customers for this store but keep groups intact
        Customer.objects.filter(store=store).delete()
        Group.objects.filter(store=store).delete()

        # Update or create groups based on the data received
        group_id_to_name = customer_data.get('group_id_to_name', {})
        for group_id, group_name in group_id_to_name.items():
            Group.objects.get_or_create(
                group_id=group_id,
                store=store,
                defaults={'name': group_name}  # Corrected to ensure it's a dictionary
            )

        # Add new customers and associate them with groups
        customers_list = customer_data['customers']
        for customer in customers_list:
    # Create the customer entry
            customer_obj = Customer.objects.create(
                store=store,
                customer_first_name=customer['first_name'],
                customer_name=customer['name'],
                customer_email=customer['email'],
                customer_phone=customer['phone'],
                customer_location=customer['location'],
                customer_updated_at=customer['updated_at'],
            )

            # Debug print: check group IDs for the customer
            group_ids = customer.get('groups', [])

            # Associate the customer with groups
            groups = Group.objects.filter(group_id__in=group_ids, store=store)
            customer_obj.customer_groups.set(groups)

        return JsonResponse({'status': 'success', 'type': 'success', 'message': 'تم تحديث قاعدة البيانات بنجاح.'}, status=200)

    except Exception as e:
        logger.error("Error during sync: %s", e, exc_info=True)
        return JsonResponse({'status': 'error', 'type': 'error', 'message': 'حدث خطأ أثناء المزامنة.'}, status=500)