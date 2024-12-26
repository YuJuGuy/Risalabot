from django import forms
from django.contrib.auth.forms import UserCreationForm
from . models import User , Campaign, Flow, StaticBotStart, StaticBot
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
        fields = ['name', 'scheduled_time', 'msg', 'customers_group', 'status', 'delay_in_seconds']
        labels = {
            'name': 'اسم الحملة',
            'scheduled_time': 'وقت المخطط',
            'msg': 'نص الرسالة',
            'customers_group': 'مجموعة العملاء',
            'status': 'حالة الحملة',
            'delay_in_seconds': 'التاخير بين الرسائل بالثواني',
        }
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
            choices=[('', 'اختر مجموعة العملاء')] + [(group.group_id, group.name) for group in store_groups.order_by('-group_id')]
        )
        # Optional: Set HTML attributes for 'customers_group'
        self.fields['customers_group'].widget.attrs.update({'class': 'custom-select'})

        for field_name, field in self.fields.items():
        # Set custom error messages
            field.error_messages = {
                'required': f'يجب إدخال {self.Meta.labels[field_name]}'
            }


    
    def get_custom_errors(self):
        """
        Return errors with field names replaced by their labels in Arabic.
        """
        errors = {}
        for field_name, field_errors in self.errors.items():
            label = self.Meta.labels.get(field_name, field_name)
            errors[label] = list(field_errors)
        return errors
        
        
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
        fields = ['name', 'trigger']
        labels = {
            'name': 'اسم الأتمتة',
            'trigger': 'المشغل',  # Change the label for 'trigger' to 'المشغل'
        }
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'أدخل اسم الأتمتة'}),
            'trigger': forms.Select(attrs={'placeholder': 'اختر المشغل'}),
        }

    def __init__(self, *args, **kwargs):
        super(FlowForm, self).__init__(*args, **kwargs)
        # Customize the empty label for the trigger field
        self.fields['trigger'].empty_label = "اختر المشغل"
        
        for field_name, field in self.fields.items():
            # Set custom error messages
            field.error_messages = {
                'required': f'يجب إدخال {self.Meta.labels[field_name]}'
            }
    
    def get_custom_errors(self):
        """
        Return errors with field names replaced by their labels in Arabic.
        """
        errors = {}
        for field_name, field_errors in self.errors.items():
            label = self.Meta.labels.get(field_name, field_name)
            errors[label] = list(field_errors)
        return errors

class StaticBotStartForm(forms.ModelForm):
    class Meta:
        model = StaticBotStart
        fields = ['enabled', 'hours',  'return_message']

        labels = {
            'enabled': 'مفعل',
            'hours': 'الساعات',
            'return_message': 'الرسالة المرجعية',

        }
        widgets = {
            'enabled': forms.CheckboxInput(),
            'hours': forms.NumberInput(),
            'return_message': forms.Textarea(attrs={'placeholder': 'ادخل الرسالة المرجعية هنا'}),

        }


    def __init__(self, *args, **kwargs):
        super(StaticBotStartForm, self).__init__(*args, **kwargs)
            # Customize the empty label for the trigger field            
        for field_name, field in self.fields.items():
                # Set custom error messages
            field.error_messages = {
                'required': f'يجب إدخال {self.Meta.labels[field_name]}'
            }
            
        
    def get_custom_errors(self):
        errors = {}
        for field_name, field_errors in self.errors.items():
            label = self.Meta.labels.get(field_name, field_name)
            errors[label] = list(field_errors)
        return errors



class StaticBotForm(forms.ModelForm):
    class Meta:
        model = StaticBot
        fields = ['message', 'return_message', 'condition']

        labels = {
            'message': 'الرسالة',
            'return_message': 'الرسالة المرجعية',
            'condition': 'الشرط',
        }
        widgets = {
            'message': forms.Textarea(attrs={'placeholder': 'ادخل الرسالة هنا'}),
            'return_message': forms.Textarea(attrs={'placeholder': 'ادخل الرسالة المرجعية هنا'}),
            'condition': forms.Select(attrs={'placeholder': 'اختر الشرط'}),
        }

    def __init__(self, *args, **kwargs):
        super(StaticBotForm, self).__init__(*args, **kwargs)  # Correctly call the parent __init__
        for field_name, field in self.fields.items():
            # Set custom error messages
            field.error_messages = {
                'required': f'يجب إدخال {self.Meta.labels[field_name]}'
            }

    def get_custom_errors(self):
        errors = {}
        for field_name, field_errors in self.errors.items():
            label = self.Meta.labels.get(field_name, field_name)
            errors[label] = list(field_errors)
        return errors






