from django.contrib import admin

from .models import Organization, PaymentGatewayConfig, Payment

@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "active"]

@admin.register(PaymentGatewayConfig)
class PaymentGatewayConfigAdmin(admin.ModelAdmin):
    list_display = ["organization", "gateway", "active"]
    list_filter = ["gateway", "active"]

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ["id", "organization", "status", "amount", "created_at"]
    list_filter = ["status", "organization"]
