from django.db import models

# Create your models here.


class Platform(models.Model):
    name = models.CharField(max_length=100)
    domain = models. CharField(max_length=200, blank=True, null=True)

    
    def __str__(self):
        return self.name
    

class Product(models.Model):
    name = models.CharField(max_length=100)
    monthly_price = models.DecimalField(max_digits=10, decimal_places=2)
    biweekly_price = models.DecimalField(max_digits=10, decimal_places=2) 

    def __str__(self):
        return self.name   


class Payment(models.Model):
    STATUS_CHOICES = [
        ("initiated", "Initiated"),
        ("pending", "Pending"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("reversed", "Reversed"),
    ]

    user_id = models.IntegerField()
    platform = models.ForeignKey(Platform, on_delete=models.CASCADE, null=True, blank=True) 
    product = models.ForeignKey(Product, on_delete=models.CASCADE, null=True, blank=True)    
    phone = models.CharField(max_length=20)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    duration = models.CharField(max_length=20, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="initiated")
    transaction_reference = models.CharField(max_length=100, null=True, blank=True)
    kopokopo_location = models.CharField(max_length=255, null=True, blank=True)
    raw_payload = models.JSONField(default=dict, blank=True)
    currency = models.CharField(max_length=10, default="KES")
    transaction_uuid = models.CharField(max_length=100, null=True, blank=True)
    reference_number = models.CharField(max_length=100, null=True, blank=True)
    payment_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    organization = models.ForeignKey("Organization", on_delete=models.CASCADE, null=True, blank=True)


    laravel_payment_id = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f"Payment {self.id} - {self.status}"



class Organization(models.Model):
    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=100)
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.code})"


GATEWAY_CHOICES = [
    ("KOPOKOPO", "KopoKopo"),
    ("CYBERSOURCE", "CyberSource"),
    ("MPESA", "M-PESA"),
]

class PaymentGatewayConfig(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="gateway_configs")
    gateway = models.CharField(max_length=50, choices=GATEWAY_CHOICES)

    client_id = models.CharField(max_length=255, default="default_client_id_here")
    client_secret = models.CharField(max_length=255)
    api_key = models.CharField(max_length=255, blank=True, null=True)
    till_number = models.CharField(max_length=50, blank=True, null=True)
    base_url = models.URLField(max_length=500)
    callback_url = models.URLField(max_length=500)
    active = models.BooleanField(default=True)

    mpesa_consumer_key = models.CharField(max_length=255, blank=True, null=True)
    mpesa_consumer_secret = models.CharField(max_length=255, blank=True, null=True)
    mpesa_shortcode = models.CharField(max_length=50, blank=True, null=True)
    mpesa_passkey = models.CharField(max_length=255, blank=True, null=True)
    mpesa_initiator_name = models.CharField(max_length=255, blank=True, null=True)
    mpesa_initiator_password = models.CharField(max_length=255, blank=True, null=True)
    mpesa_environment = models.CharField(max_length=20, choices=[("sandbox","Sandbox"),("production","Production")], default="sandbox")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("organization", "gateway")

    def __str__(self):
        return f"{self.organization.code} - {self.gateway}"

    