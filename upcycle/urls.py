from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from myapp import views

urlpatterns = [
    # Admin & Authentication
    path('admin/', admin.site.urls),
    path('', views.login_view, name='login'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('home/', views.home_view, name='home'),
    path('profile/', views.profile_view, name='profile'),

    # Product Management
    path('buyproduct/', views.buy_product_view, name='buy_product'),
    path('sellproduct/', views.sell_product_view, name='sell_product'),
    path('explore_collection/', views.explore_collection_view, name='explore_collection'),

    # Shopping Cart
    path('cart/', views.cart_view, name='cart'),
    path('add_to_cart/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('remove_from_cart/<int:product_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('delete_from_cart/<int:product_id>/', views.delete_from_cart, name='delete_from_cart'),

    # Checkout & Stripe Payments
    path('checkout/', views.checkout_view, name='checkout'),
    path('checkout/success/', views.payment_success, name='payment_success'),
    path('checkout/cancel/', views.payment_cancel, name='payment_cancel'),

    # Designer Hiring
    path('hire-designer/', views.hire_designer_view, name='hire_designer'),
    path('hire-designer/request/', views.hire_designer_request, name='hire_designer_request'),

    # AI Chatbot (Groq)
    path('chat/', views.chat_page, name='chat'),
    path('chat/send/', views.chat_send, name='chat_send'),
    path('chat/clear/', views.chat_clear, name='chat_clear'),

    # Odoo Sync API
    path('api/v1/odoo-sync/', include('odoo_sync.urls')),
]

# Media Files (Images) handling in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
