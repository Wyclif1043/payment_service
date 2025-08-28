from django.urls import path
from .views import InitiatePayment, PaymentCallback
from .views import InitiateCardPayment
from .views import CyberSourceNotification
from .views import CyberSourceResponse



urlpatterns = [
    path("initiate/", InitiatePayment.as_view(), name="initiate-payment"),
    path("callback/", PaymentCallback.as_view(), name="payment-callback"),
    path("card/initiate/", InitiateCardPayment.as_view(), name="initiate-card-payment"),
    path("notification/", CyberSourceNotification.as_view(), name="cybersource-notification"),
    path("response/", CyberSourceResponse.as_view(), name="cybersource-response"),
    
]
