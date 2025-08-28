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
    platform = models.ForeignKey(Platform, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    phone = models.CharField(max_length=20)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    duration = models.CharField(max_length=20)
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

    laravel_payment_id = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f"Payment {self.id} - {self.status}"

    