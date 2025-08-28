from django.shortcuts import render
import requests, hmac, hashlib, json, logging
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Payment, Product, Platform
from .serializers import PaymentSerializer
import uuid, datetime
from .utils import sign_fields
import requests
import uuid, hmac, hashlib, base64, logging


logger = logging.getLogger(__name__)

class InitiatePayment(APIView):
    def post(self, request):
        data = request.data
        # logging dat for test
        import pprint
        print("🔥 InitiatePayment request received")
        print(pprint.pformat(data))

        try:
            # ✅ Use price directly from Laravel (source of truth)
            price = data.get("amount")
            if not price:
                return Response({"error": "Amount is required"}, status=400)

            phone = self.format_phone(data["phone"])
            if not phone:
                return Response({"error": "Invalid phone"}, status=400)

            # still keep reference to platform/product if sent
            platform = None
            product = None
            if "platform_id" in data:
                try:
                    platform = Platform.objects.get(id=data["platform_id"])
                except Platform.DoesNotExist:
                    logger.warning("Platform not found, skipping")

            if "product_id" in data:
                try:
                    product = Product.objects.get(id=data["product_id"])
                except Product.DoesNotExist:
                    logger.warning("Product not found, skipping")

            # Save payment
            payment = Payment.objects.create(
                laravel_payment_id=data.get("payment_id"),
                user_id=data["user_id"],
                platform=platform,
                product=product,
                phone=phone,
                amount=price,
                duration=data.get("duration", "manual"),
                status="initiated",
                raw_payload={"request": data},
            )

            # Get access token
            token_resp = requests.post(
                f"{settings.KOPOKOPO_BASE_URL}/oauth/token",
                data={"grant_type": "client_credentials"},
                auth=(settings.KOPOKOPO_CLIENT_ID, settings.KOPOKOPO_CLIENT_SECRET),
            )

            if token_resp.status_code != 200:
                payment.status = "failed"
                payment.save()
                return Response({"error": "Token request failed"}, status=500)

            access_token = token_resp.json().get("access_token")

            # STK Push request
            stk_payload = {
                "payment_channel": "M-PESA STK Push",
                "till_number": settings.KOPOKOPO_TILL_NUMBER,
                "subscriber": {
                    "first_name": data["first_name"],
                    "last_name": data["last_name"],
                    "phone_number": phone,
                    "email": data.get("email", ""),
                },
                "amount": {"currency": "KES", "value": int(float(price))},
                "metadata": {
                    "payment_id": str(payment.id), 
                    "customer_id": str(data["user_id"]),
                },
                "_links": {"callback_url": settings.KOPOKOPO_CALLBACK_URL},
            }

            stk_resp = requests.post(
                f"{settings.KOPOKOPO_BASE_URL}/api/v1/incoming_payments",
                headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
                json=stk_payload,
            )

            if stk_resp.status_code == 201:
                payment.status = "pending"
                payment.kopokopo_location = stk_resp.headers.get("Location")
                payment.save()
                return Response({"message": "Payment initiated", "payment_id": payment.id}, status=200)
            else:
                payment.status = "failed"
                payment.save()
                return Response({"error": "STK Push failed", "details": stk_resp.json()}, status=400)

        except Exception as e:
            logger.error(f"Payment initiation error: {e}")
            return Response({"error": "Server error"}, status=500)

    def format_phone(self, phone):
        phone = str(phone).replace("+", "")
        if phone.startswith("0"):
            return "254" + phone[1:]
        if phone.startswith("254"):
            return phone
        return None


class PaymentCallback(APIView):
    def post(self, request):
        signature = request.headers.get("X-KopoKopo-Signature")
        payload = request.body

        calc_sig = hmac.new(
            settings.KOPOKOPO_API_KEY.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()

        if signature != calc_sig:
            logger.error(f"Invalid signature. Header: {signature}, Calculated: {calc_sig}")
            return Response({"error": "Invalid signature"}, status=401)

        data = json.loads(payload)
        attributes = data.get("data", {}).get("attributes", {})
        status_value = attributes.get("status")
        metadata = attributes.get("metadata", {})
        resource = attributes.get("event", {}).get("resource", {})
        payment_id = metadata.get("payment_id")

        try:
            payment = Payment.objects.get(id=payment_id)

            if status_value == "Success":
                payment.status = "completed"
            elif status_value == "Reversed":
                payment.status = "reversed"
            else:
                payment.status = "failed"

            payment.raw_payload.update({"callback": attributes})
            payment.save()

            laravel_url = settings.LARAVEL_UPDATE_URL
            payload = {
                "payment_id": payment.laravel_payment_id,
                "status": payment.status,
                "transaction_reference": resource.get("reference"),
                "amount": resource.get("amount"),
                "currency": resource.get("currency"),
                "resource": resource,  
                "metadata": metadata,   
                "rawData": data,        
            }


            try:
                resp = requests.post(laravel_url, json=payload, timeout=10)
                if resp.status_code == 200:
                    logger.info(f"✅ Notified Laravel successfully: {payload}")
                else:
                    logger.error(
                        f"❌ Laravel update failed. "
                        f"Status {resp.status_code}, Response: {resp.text}, Payload: {payload}"
                    )
            except Exception as e:
                logger.error(f"🔥 Failed to notify Laravel: {str(e)}, Payload: {payload}")

        except Payment.DoesNotExist:
            logger.error(f"Payment not found: {payment_id}")

        return Response({"status": "ok"})
            



class InitiateCardPayment(APIView):
    def post(self, request):
        try:
            data = request.data
            product = Product.objects.get(id=data["product_id"])
            platform = Platform.objects.get(id=data.get("platform_id"))

            amount = float(data["price"])
            currency = data["currency"]

            transaction_uuid = str(uuid.uuid4())
            reference_number = f"EXO-{int(datetime.datetime.now().timestamp())}-{data['user_id']}"

            fields = {
                "access_key": settings.CYBERSOURCE_ACCESS_KEY,
                "profile_id": settings.CYBERSOURCE_PROFILE_ID,
                "transaction_uuid": transaction_uuid,
                "signed_field_names": "access_key,profile_id,transaction_uuid,signed_field_names,unsigned_field_names,amount,currency,reference_number,transaction_type,signed_date_time,locale",
                "unsigned_field_names": "",
                "signed_date_time": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "locale": "en",
                "transaction_type": "sale",
                "reference_number": reference_number,
                "amount": str(amount),
                "currency": currency,
            }

            fields["signature"] = sign_fields(fields, settings.CYBERSOURCE_SECRET_KEY)

            payment = Payment.objects.create(
                user_id=data["user_id"],
                product=product,
                platform=platform,
                amount=amount,
                currency=currency,
                duration=data.get("duration", "manual"),
                status="pending",
                transaction_uuid=transaction_uuid,
                reference_number=reference_number,
                payment_data=fields,
            )

            return Response({
                "status": True,
                "payment_id": payment.id,
                "cybersource_url": settings.CYBERSOURCE_API_URL,  # e.g., https://testsecureacceptance.cybersource.com/pay
                "payment_data": fields
            })

        except Product.DoesNotExist:
            return Response({"error": "Invalid product"}, status=400)
        except Platform.DoesNotExist:
            return Response({"error": "Invalid platform"}, status=400)
        except Exception as e:
            return Response({"error": str(e)}, status=500)


# --- Step 2: CyberSource Notification ---
class CyberSourceNotification(APIView):
    def post(self, request):
        data = request.data
        received_signature = data.get("signature")
        params = {k: v for k, v in data.items() if k != "signature"}

        calculated_signature = sign_fields(params, settings.CYBERSOURCE_SECRET_KEY)

        if received_signature != calculated_signature:
            return Response({"error": "Invalid signature"}, status=403)

        transaction_uuid = data.get("req_transaction_uuid")
        reference_number = data.get("req_reference_number")
        decision = data.get("decision")
        transaction_id = data.get("transaction_id")

        try:
            payment = Payment.objects.filter(
                transaction_uuid=transaction_uuid
            ).first() or Payment.objects.filter(
                reference_number=reference_number
            ).first()

            if not payment:
                return Response({"error": "Payment not found"}, status=404)

            status_map = {
                "ACCEPT": "completed",
                "DECLINE": "failed",
                "REVIEW": "under_review",
                "ERROR": "error"
            }
            payment.status = status_map.get(decision.upper(), "unknown")
            payment.transaction_id = transaction_id
            payment.response_data = data
            payment.save()

            return Response({"status": "received"})
        except Exception as e:
            return Response({"error": str(e)}, status=500)


# --- Step 3: CyberSource Response (redirect after payment) ---
class CyberSourceResponse(APIView):
    def post(self, request):
        data = request.data
        received_signature = data.get("signature")
        params = {k: v for k, v in data.items() if k != "signature"}

        calculated_signature = sign_fields(params, settings.CYBERSOURCE_SECRET_KEY)

        if received_signature != calculated_signature:
            return Response({"error": "Invalid response signature"}, status=403)

        decision = data.get("decision")
        transaction_uuid = data.get("req_transaction_uuid")

        payment = Payment.objects.filter(transaction_uuid=transaction_uuid).first()
        if not payment:
            return Response({"error": "Payment not found"}, status=404)

        # Same status mapping
        status_map = {
            "ACCEPT": "completed",
            "DECLINE": "failed",
            "REVIEW": "under_review",
            "ERROR": "error"
        }
        payment.status = status_map.get(decision.upper(), "unknown")
        payment.response_data = data
        payment.save()

        return Response({"status": payment.status})


# --- Step 4: Cancel endpoint ---
class CyberSourceCancel(APIView):
    def post(self, request):
        transaction_uuid = request.data.get("req_transaction_uuid")
        if transaction_uuid:
            Payment.objects.filter(transaction_uuid=transaction_uuid).update(status="canceled")
        return Response({"status": "canceled"})



            
