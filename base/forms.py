from django import forms
from django.contrib.auth.forms import UserCreationForm
from . models import User , UserEvent

class CreateUserForm(UserCreationForm):
    username = forms.CharField(label='اسم المستخدم', max_length=150)
    email = forms.EmailField(label='البريد الإلكتروني')
    password1 = forms.CharField(label='كلمة المرور', widget=forms.PasswordInput)
    password2 = forms.CharField(label='تأكيد كلمة المرور', widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

class UserEventForm(forms.ModelForm):
    class Meta:
        model = UserEvent
        fields = ['event_type', 'subcategory', 'message_template']

    def __init__(self, *args, **kwargs):
        super(UserEventForm, self).__init__(*args, **kwargs)

        instance = kwargs.get('instance')
        if instance and instance.event_type.label == 'تحديث حالة الطلب':  # Check with the label instead of name
            self.fields['subcategory'].widget = forms.Select(choices=UserEvent.ORDER_UPDATED_SUBCATEGORIES)

        self.fields['event_type'].widget.attrs.update({
            'onchange': 'updateSubcategoryVisibility(this.value);'
        })

        self.fields['message_template'].widget.attrs.update({
            'placeholder': 'Enter your message here...'
        })