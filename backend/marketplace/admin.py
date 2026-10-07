from django.contrib import admin

from .models import Client, Product, UserProfile


@admin.action(description="Approve selected products for public storefront")
def approve_products(modeladmin, request, queryset):
    queryset.update(status=Product.STATUS_APPROVED)


@admin.action(description="Reject selected products")
def reject_products(modeladmin, request, queryset):
    queryset.update(status=Product.STATUS_REJECTED)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "client", "price", "status"]
    list_filter = ["status", "client"]
    search_fields = ["name", "client__name"]
    actions = [approve_products, reject_products]


admin.site.register(Client)
admin.site.register(UserProfile)
