from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser, Product

# User Registration Form
class CustomUserCreationForm(UserCreationForm):
    full_name = forms.CharField(max_length=100, required=True, label="Full Name")
    email = forms.EmailField(required=True, label="Email Address")

    USER_TYPE_CHOICES = [
        ('buyer', 'Buyer'),
        ('seller', 'Seller')
    ]
    user_type = forms.ChoiceField(choices=USER_TYPE_CHOICES, required=True, label="User Type")

    class Meta:
        model = CustomUser
        fields = ('full_name', 'email', 'password1', 'password2', 'user_type')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.username = self.cleaned_data['email']
        user.full_name = self.cleaned_data['full_name']
        user.user_type = self.cleaned_data['user_type']

        if commit:
            user.save()
        return user

# Product Creation Form
class ProductForm(forms.ModelForm):

     IS_UPCYCLED_CHOICES = [
        (True, 'Yes'),
        (False, 'No'),
    ]

     is_upcycled = forms.ChoiceField(
        choices=IS_UPCYCLED_CHOICES,
        widget=forms.RadioSelect,  # Use radio buttons for better UX
        required=True,
        label="Is this product upcycled?"
    )

     class Meta:
        model = Product
        fields = [
            'name',
            'category',
            'description',
            'price', 
            'discount_percentage',
            'quantity',
            'materials',
            'shipping_info',
            'image',
            'is_available'
        ]
        widgets = {
            'is_available': forms.HiddenInput(),
            'discount_percentage': forms.NumberInput(attrs={'min': 0, 'max': 100})
        }