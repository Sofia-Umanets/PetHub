from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from accounts.models import CustomUser
from allauth.account.forms import SignupForm
from django import forms
from django.core.exceptions import ValidationError
import phonenumbers
from django.utils import timezone

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True, label='Email')
    
    class Meta:
        model = get_user_model()
        fields = ('email', 'username', 'avatar')

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if get_user_model().objects.filter(email=email).exists():
            raise ValidationError('Этот email уже используется')
        return email

class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = get_user_model()
        fields = ('email', 'username')

class CustomSignupForm(SignupForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop('password2', None)
        self.fields['email'].required = True
        self.fields['email'].label = 'Email'

    def clean_password2(self):
        return self.cleaned_data.get('password1')

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if get_user_model().objects.filter(email=email).exists():
            raise ValidationError('Этот email уже используется')
        return email


class UserEditForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'avatar', 'phone', 'birth_date', 'bio']
        widgets = {
            'birth_date': forms.DateInput(attrs={'type': 'date'}),
            'bio': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['avatar'].required = False
        self.fields['avatar'].widget.attrs.update({
            'accept': 'image/*'
        })

    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if phone:
            try:
                parsed = phonenumbers.parse(phone, "RU")
                if not phonenumbers.is_valid_number(parsed):
                    raise forms.ValidationError("Введите корректный номер телефона")
                return phonenumbers.format_number(
                    parsed, 
                    phonenumbers.PhoneNumberFormat.INTERNATIONAL
                )
            except phonenumbers.NumberParseException:
                raise forms.ValidationError("Введите корректный номер телефона")
        return phone

    def save(self, commit=True):
        user = super().save(commit=False)
        
        if 'avatar' in self.changed_data:
            if user.avatar: 
                user.avatar.delete(save=False)
            user.avatar = self.cleaned_data['avatar']
        
        if commit:
            user.save()
        
        return user