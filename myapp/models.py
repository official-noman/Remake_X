from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from decimal import Decimal

# Custom User Model
class CustomUser(AbstractUser):
    full_name = models.CharField(max_length=100, default='')
    email = models.EmailField(unique=True)

    USER_TYPE_CHOICES = [
        ('buyer', 'Buyer'),
        ('seller', 'Seller'),
    ]
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES, default='buyer')

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return self.email

# Product Model
class Product(models.Model):
    CATEGORY_CHOICES = [
        ('furniture', 'Furniture'),
        ('decor', 'Home Decor'),
        ('fashion', 'Fashion & Accessories'),
        ('garden', 'Garden & Outdoor'),
        ('art', 'Art & Collectibles'),
        ('other', 'Other'),
    ]
    
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_percentage = models.PositiveIntegerField(default=0)
    quantity = models.PositiveIntegerField(default=1)
    materials = models.CharField(
        max_length=255,
        default='Not specified')
    shipping_info = models.TextField(blank=True,  default='Standard shipping'  )
    image = models.ImageField(upload_to='products/')
    is_available = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    is_upcycled = models.BooleanField(default=False)

    def discounted_price(self):
        discount = Decimal(self.discount_percentage) / 100
        return self.price * (1 - discount)

    def __str__(self):
        return f"{self.name} - ${self.discounted_price():.2f}"