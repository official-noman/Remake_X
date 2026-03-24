from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from myapp import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.login_view, name='login'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('home/', views.home_view, name='home'),
    path('buyproduct/', views.buy_product_view, name='buy_product'),
    path('sellproduct/', views.sell_product_view, name='sell_product'),
    path('explore_collection/', views.explore_collection_view, name='explore_collection'),
    path('cart/', views.cart_view, name='cart'),
    path('add_to_cart/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('remove_from_cart/<int:product_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('delete_from_cart/<int:product_id>/', views.delete_from_cart, name='delete_from_cart'),
    path('checkout/', views.checkout_view, name='checkout'),
    path('hire-designer/', views.hire_designer_view, name='hire_designer'),
    # path('chat/', views.chat_view, name='chat'),
    path('chat/',        views.chat_page,  name='chat'),
path('chat/send/',   views.chat_send,  name='chat_send'),
path('chat/clear/',  views.chat_clear, name='chat_clear'),
path('checkout/',         views.checkout_view,   name='checkout'),
path('checkout/success/', views.payment_success, name='payment_success'),
path('checkout/cancel/',  views.payment_cancel,  name='payment_cancel'),
path('hire-designer/request/', views.hire_designer_request, name='hire_designer_request'),
path('profile/', views.profile_view, name='profile'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
