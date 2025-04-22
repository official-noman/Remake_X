from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import render
from myapp.views import chat_view
from django.contrib import admin
from django.urls import path, include
from myapp.views import (
    home_view,
    login_view,
    logout_view,
    register_view,
    buy_product_view,
    sell_product_view,
    explore_collection_view,
    cart_view,
    add_to_cart,
    remove_from_cart,
    delete_from_cart,
    checkout_view,
    hire_designer_view
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', login_view, name='login'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('register/', register_view, name='register'),
    path('home/', home_view, name='home'),
    path('buyproduct/', buy_product_view, name='buy_product'),
    path('sellproduct/', sell_product_view, name='sell_product'),
    path('explore_collection/', explore_collection_view, name='explore_collection'),
    path('cart/', cart_view, name='cart'),
    path('add_to_cart/<int:product_id>/', add_to_cart, name='add_to_cart'),
    path('remove_from_cart/<int:product_id>/', remove_from_cart, name='remove_from_cart'),
    path('delete_from_cart/<int:product_id>/', delete_from_cart, name='delete_from_cart'),
    path('checkout/', checkout_view, name='checkout'),
    path('hire-designer/', hire_designer_view, name='hire_designer'),
    ##path('generate-image/', views.generate_image, name='generate_image'),
    path('', include('myapp.urls')),  # 👈 Replace with your app name
    
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)