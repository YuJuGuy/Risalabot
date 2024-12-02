#Customer Views

from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from base.decorators import check_token_validity
from base.models import UserStoreLink, Customer, Group
from django.contrib import messages
from django.db.models import Count
from base.forms import GroupCreationForm
from base.apis import create_customer_group, delete_customer_group


@login_required(login_url='login')
@check_token_validity
def customers_view(request, context=None):
    if context is None:
        context = {}
    try:
        store = UserStoreLink.objects.get(user=request.user).store
    except UserStoreLink.DoesNotExist:
        logger.error(f"No store linked to user {request.user.id}")
        return redirect('dashboard')
    


    form = GroupCreationForm()
    if request.method == 'POST':
        form = GroupCreationForm(request.POST)

        if form.is_valid():
            group_name = form.cleaned_data['name']
            conditions = form.cleaned_data['conditions']
            response = create_customer_group(request.user, group_name, conditions)
            
            if response.get('success'):
                # Return a JSON response on successful creation
                return JsonResponse({'status': 'success', 'type': 'success','message': 'تم إنشاء المجموعة بنجاح.'}, status=200)
            else:
                # Return JSON with error messages
                error_message = response.get('error', {}).get('message', 'حدث خطأ ما.')
                error_fields = response.get('error', {}).get('fields', {})
                message = {field: messages_list for field, messages_list in error_fields.items()}
                return JsonResponse({'status': 'error', 'type': 'error','message': error_message}, status=400)
        else:
            return JsonResponse({'status': 'error', 'type': 'error','message': 'فشل التحقق من صحة النموذج.'}, status=400)

    context.update({
        'form': form,
    })
    
    return render(request, 'base/customer_list.html', context)




@login_required(login_url='login')
def get_customers(request):
    try:
        # Get the store associated with the logged-in user
        store = UserStoreLink.objects.get(user=request.user).store

        # Retrieve customers for the specific store
        customers_list = Customer.objects.filter(store=store)

        # Prepare customer data
        customers_data = [{
            'name': customer.customer_name,
            'email': customer.customer_email,
            'phone': customer.customer_phone,
            'location': customer.customer_location,
            'groups': list(customer.customer_groups.values_list('name', flat=True).exclude(name='جميع العملاء')),  # Group IDs
            'updated_at': customer.customer_updated_at.strftime('%Y-%m-%d %H:%M')
        } for customer in customers_list]
        

        # Calculate group counts

        # Create a dictionary of group IDs to names
        group_data = (
            Group.objects.filter(store=store).exclude(name='جميع العملاء')
            .annotate(customer_count=Count('customers'))  # Count related customers for each group
            .values('group_id', 'name', customer_count=Count('customers'))  # Include group ID, name, and customer count

        )

        # Convert to list of dictionaries for easier JSON handling
        group_data_list = list(group_data)
        
        return JsonResponse({
            'customers': customers_data,
            'group_data': group_data_list,  # List of dictionaries with 'name' and 'customer_count'
            'total_count': len(customers_list),
        }, status=200)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required(login_url='login')
def delete_customer_list(request, group_id):
    if request.method == "POST":
        response = delete_customer_group(request.user, group_id)
        if response.get('success'):
            return JsonResponse({'status': 'success', 'type': 'success','message': 'تم حذف المجموعة بنجاح.'}, status=200)
        else:
            return JsonResponse({'status': 'error', 'type': 'error','message': 'فشل حذف المجموعة.'}, status=400)
    return JsonResponse({'status': 'error', 'type': 'error','message': 'طريقة الطلب غير صالحة.'}, status=405)
