from django import forms
from django.contrib.auth.forms import UserCreationForm
from . models import User

class CreateUserForm(UserCreationForm):
    username = forms.CharField(label='اسم المستخدم', max_length=150)
    email = forms.EmailField(label='البريد الإلكتروني')
    password1 = forms.CharField(label='كلمة المرور', widget=forms.PasswordInput)
    password2 = forms.CharField(label='تأكيد كلمة المرور', widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']
