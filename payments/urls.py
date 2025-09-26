from django.urls import path, include   # <-- add include here
from rest_framework.routers import DefaultRouter
from .views import (
    InitiatePayment, PaymentCallback, InitiateCardPayment,
    CyberSourceNotification, CyberSourceResponse,
    OrganizationViewSet, PaymentGatewayConfigViewSet
)

router = DefaultRouter()
router.register(r'organizations', OrganizationViewSet, basename='organization')
router.register(r'gateway-configs', PaymentGatewayConfigViewSet, basename='gateway-config')

urlpatterns = [
    path('', include(router.urls)),

    path("initiate/", InitiatePayment.as_view(), name="initiate-payment"),
    path("callback/", PaymentCallback.as_view(), name="payment-callback"),
    path("card/initiate/", InitiateCardPayment.as_view(), name="initiate-card-payment"),
    path("notification/", CyberSourceNotification.as_view(), name="cybersource-notification"),
    path("response/", CyberSourceResponse.as_view(), name="cybersource-response"),
]
