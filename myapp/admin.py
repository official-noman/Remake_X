from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Product
from django.utils.html import format_html

# CustomUser Admin
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ('email', 'full_name', 'user_type', 'is_staff', 'is_active')
    list_filter = ('user_type', 'is_staff', 'is_active')
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('full_name', 'user_type')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'full_name', 'user_type', 'password1', 'password2', 'is_staff', 'is_active')
        }),
    )
    search_fields = ('email', 'full_name')
    ordering = ('email',)

# Register CustomUser
admin.site.register(CustomUser, CustomUserAdmin)

# Product Admin
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'discount_percentage', 'discounted_price', 'image_preview', 'is_available', 'is_upcycled')
    list_filter = ('discount_percentage', 'is_upcycled')
    search_fields = ('name', 'description')
    readonly_fields = ('image_preview',)
    list_editable = ('is_upcycled', 'is_available',)
    
    def image_preview(self, obj):
        if obj.image:
            return f'<img src="{obj.image.url}" width="100" height="100" />'
        return "(No Image)"
    
    image_preview.allow_tags = True
    image_preview.short_description = "Preview"

    # def is_upcycled_display(self, obj):
    #     return format_html("✅") if obj.is_upcycled else format_html("❌")
    
    # is_upcycled_display.short_description = "Is Upcycled"
    # is_upcycled_display.admin_order_field = "is_upcycled"

# Register Product
admin.site.register(Product, ProductAdmin)