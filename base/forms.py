from django import forms
from django.contrib.auth.forms import UserCreationForm
from . models import User , Campaign, Flow, FlowActionTypes
from django.core.exceptions import ValidationError
import json

class CreateUserForm(UserCreationForm):
    username = forms.CharField(label='اسم المستخدم', max_length=150)
    email = forms.EmailField(label='البريد الإلكتروني')
    password1 = forms.CharField(label='كلمة المرور', widget=forms.PasswordInput)
    password2 = forms.CharField(label='تأكيد كلمة المرور', widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']


        
        
class CampaignForm(forms.ModelForm):
    class Meta:
        model = Campaign
        fields = ['name', 'scheduled_time', 'msg', 'customers_group', 'status']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'أدخل اسم الحملة'}),
            'scheduled_time': forms.DateTimeInput(
                attrs={
                    'type': 'datetime-local',
                    'placeholder': 'Scheduled Time'
                }
            ),
            'msg': forms.Textarea(attrs={'placeholder': 'أدخل نص الرسالة هنا'}),
            # 'customers_group' is a Select widget; placeholders don't apply directly
            'status': forms.Select(attrs={'placeholder': 'حالة الحملة'}, choices=[('scheduled','جدولة'), ('draft', 'مسودة')]), # add choices to the widget
        }

    def __init__(self, *args, **kwargs):
        store_groups = kwargs.pop('store_groups', [])
        super(CampaignForm, self).__init__(*args, **kwargs)
        self.fields['customers_group'].widget = forms.Select(
            choices=[('', 'اختر مجموعة العملاء')] + [(group.id, group.name) for group in store_groups]
        )
        # Optional: Set HTML attributes for 'customers_group'
        self.fields['customers_group'].widget.attrs.update({'class': 'custom-select'})
        
        
class GroupCreationForm(forms.Form):
    name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'placeholder': 'اسم المجموعة'})
    )

    def clean(self):
        cleaned_data = super().clean()
        conditions = []
        condition_fields = [key for key in self.data.keys() if key.startswith('condition_field')]

        for field in condition_fields:
            index = field.split('-')[-1]
            condition_field = self.data.get(f'condition_field-{index}')
            symbol_field = self.data.get(f'symbol_field-{index}')

            if symbol_field == 'between':
                min_value_field = self.data.get(f'min_value_field-{index}')
                max_value_field = self.data.get(f'max_value_field-{index}')
                if min_value_field is None or max_value_field is None:
                    raise ValidationError('Both min and max values are required for "between" symbol.')
                # Validate min_value and max_value fields
                try:
                    min_value_field = int(min_value_field)
                    max_value_field = int(max_value_field)
                    if min_value_field < 0 or max_value_field < 0:
                        raise ValidationError('Values must be non-negative integers.')
                    if min_value_field >= max_value_field:
                        raise ValidationError('Min value must be less than max value.')
                except ValueError:
                    raise ValidationError('Invalid min or max value.')
                conditions.append({
                    'type': condition_field,
                    'symbol': symbol_field,
                    'min_value': min_value_field,
                    'max_value': max_value_field
                })
            else:
                value_field = self.data.get(f'value_field-{index}')
                if value_field is None:
                    raise ValidationError('Value is required.')
                # Validate value field
                try:
                    value_field = int(value_field)
                    if value_field < 0:
                        raise ValidationError(f'Value must be a non-negative integer: {value_field}')
                except ValueError:
                    raise ValidationError(f'Invalid value: {value_field}')
                conditions.append({
                    'type': condition_field,
                    'symbol': symbol_field,
                    'value': value_field
                })

        # You can add any additional validation logic here
        cleaned_data['conditions'] = conditions
        return cleaned_data
    
class FlowForm(forms.ModelForm):
    class Meta:
        model = Flow
        fields = ['name','trigger']
        labels = {
            'name': 'اسم التدفق',
            'trigger': 'المشغل',
        }
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'أدخل اسم التدفق'}),
            'trigger': forms.Select(attrs={'placeholder': 'اختر المشغل'}),
        }

    def __init__(self, *args, **kwargs):
        super(FlowForm, self).__init__(*args, **kwargs)
        # Customize the empty label for the trigger field
        self.fields['trigger'].empty_label = "اختر المشغل"
        
        

