from rest_framework import serializers
from .models import Payment
from .models import Organization, PaymentGatewayConfig

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:

        model = Payment
        fields = "__all__"



class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = "__all__"

class PaymentGatewayConfigSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)

    class Meta:
        model = PaymentGatewayConfig
        fields = "__all__"
