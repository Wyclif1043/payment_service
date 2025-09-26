from django.shortcuts import render
import requests, hmac, hashlib, json, logging
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Payment, Product, Platform, Organization, PaymentGatewayConfig
from .serializers import PaymentSerializer
import uuid, datetime
from .utils import sign_fields
import requests
import uuid, hmac, hashlib, base64, logging
import traceback
from rest_framework import viewsets
from .serializers import OrganizationSerializer
from .serializers import PaymentGatewayConfigSerializer




logger = logging.getLogger(__name__)


class OrganizationViewSet(viewsets.ModelViewSet):
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer

class PaymentGatewayConfigViewSet(viewsets.ModelViewSet):
    queryset = PaymentGatewayConfig.objects.all()
    serializer_class = PaymentGatewayConfigSerializer



class InitiatePayment(APIView):
    def post(self, request):
        try:
            data = request.data
            logger.info("InitiatePayment request received: %s", data)

            org_code = data.get("organization_code")
            try:
                org = Organization.objects.get(code=org_code, active=True)
            except Organization.DoesNotExist:
                return Response({"error": "Invalid organization code"}, status=400)

            org_config = org.gateway_configs.filter(
                gateway="KOPOKOPO", active=True
            ).first()
            if not org_config:
                return Response({"error": "No active KopoKopo config found"}, status=400)

            price = data.get("amount")
            if not price:
                return Response({"error": "Amount is required"}, status=400)

            phone = self.format_phone(data.get("phone"))
            if not phone:
                return Response({"error": "Invalid phone"}, status=400)

            platform = Platform.objects.filter(id=data.get("platform_id")).first() if data.get("platform_id") else None
            product = Product.objects.filter(id=data.get("product_id")).first() if data.get("product_id") else None

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

            token_resp = requests.post(
                f"{org_config.base_url}/oauth/token",
                data={"grant_type": "client_credentials"},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                auth=(org_config.client_id, org_config.client_secret),
            )
            logger.info("Token response: %s %s", token_resp.status_code, token_resp.text)

            if token_resp.status_code != 200:
                return Response({
                    "error": "Token request failed",
                    "status_code": token_resp.status_code,
                    "body": token_resp.text
                }, status=500)

            try:
                access_token = token_resp.json().get("access_token")
            except Exception:
                return Response({"error": "Invalid token response", "body": token_resp.text}, status=500)

            if not access_token:
                return Response({"error": "Access token missing"}, status=500)

            stk_payload = {
                "payment_channel": "M-PESA STK Push",
                "till_number": org_config.till_number,
                "subscriber": {
                    "first_name": data.get("first_name", ""),
                    "last_name": data.get("last_name", ""),
                    "phone_number": phone,
                    "email": data.get("email", ""),
                },
                "amount": {"currency": "KES", "value": int(float(price))},
                "metadata": {
                    "payment_id": str(payment.id),
                    "organization_code": org_code,
                },
                "_links": {"callback_url": org_config.callback_url},
            }

            stk_resp = requests.post(
                f"{org_config.base_url}/api/v1/incoming_payments",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                },
                json=stk_payload,
            )
            logger.info("STK Push response: %s %s", stk_resp.status_code, stk_resp.text)

            if stk_resp.status_code == 201:
                payment.status = "pending"
                payment.kopokopo_location = stk_resp.headers.get("Location")
                payment.save()
                return Response({"message": "Payment initiated", "payment_id": payment.id}, status=200)
            else:
                payment.status = "failed"
                payment.save()
                return Response({
                    "error": "STK Push failed",
                    "status_code": stk_resp.status_code,
                    "details": stk_resp.text
                }, status=400)

        except Exception as e:
            logger.error("🔥 ERROR: %s", str(e), exc_info=True)
            return Response({"error": str(e)}, status=500)

    def format_phone(self, phone):
        if not phone:
            return None
        phone = str(phone).replace("+", "")
        if phone.startswith("0"):
            return "254" + phone[1:]
        if phone.startswith("254"):
            return phone
        return None



class PaymentCallback(APIView):
    def post(self, request):
        payload = request.body

        try:
            raw_json = json.loads(payload)
            logger.info("KopoKopo Callback Raw Data: %s", json.dumps(raw_json, indent=2))
        except Exception as e:
            logger.error(f"Failed to parse callback JSON: {e}")
            return Response({"error": "Invalid JSON"}, status=400)

        attributes = raw_json.get("data", {}).get("attributes", {})
        metadata = attributes.get("metadata", {})
        org_code = metadata.get("organization_code")
        payment_id = metadata.get("payment_id")

        try:
            org = Organization.objects.get(code=org_code, active=True)
            org_config = org.gateway_configs.filter(gateway="KOPOKOPO", active=True).first()
        except Organization.DoesNotExist:
            return Response({"error": "Invalid organization code"}, status=400)

        if not org_config:
            return Response({"error": "No active config for this org"}, status=400)

        signature = request.headers.get("X-KopoKopo-Signature")
        api_key = org_config.api_key
        calc_sig = hmac.new(api_key.encode(), payload, hashlib.sha256).hexdigest()

        if signature != calc_sig:
            logger.warning("Signature mismatch. Expected=%s Got=%s", calc_sig, signature)
            return Response({"error": "Invalid signature"}, status=401)

        try:
            payment = Payment.objects.get(id=payment_id)
        except Payment.DoesNotExist:
            logger.error(f"Payment not found for ID: {payment_id}")
            return Response({"error": "Payment not found"}, status=404)

        status_value = attributes.get("status")
        resource = attributes.get("event", {}).get("resource") or {}

        if status_value == "Success":
            payment.status = "completed"
        elif status_value == "Reversed":
            payment.status = "reversed"
        else:
            payment.status = "failed"

        payment.raw_payload.update({"callback": attributes})
        payment.save()

        logger.info(f"Payment {payment.id} updated to {payment.status} for org {org_code}")

        if org_code == "76":
            notify_payload = {
                "organization_code": org_code,
                "payment_id": payment.laravel_payment_id,
                "status": payment.status,
                "transaction_reference": resource.get("reference"),
                "amount": resource.get("amount"),
                "currency": resource.get("currency"),
                "resource": resource,
                "metadata": metadata,
                "rawData": attributes,
            }
            try:
                resp = requests.post(settings.LARAVEL_UPDATE_URL, json=notify_payload, timeout=10)
                logger.info(f"Laravel notified. Status={resp.status_code}, Response={resp.text}")
            except Exception as e:
                logger.error(f"Failed to notify Laravel: {e}, Payload={notify_payload}")


        if payment.status == "completed":
            partner_payload = {"Org_Code": org_code, "Amount": resource.get("amount")}
            try:
                partner_url = getattr(settings, "PARTNER_UPDATE_URL", None)
                if partner_url:
                    p_resp = requests.post(partner_url, json=partner_payload, timeout=10)
                    logger.info(f"Partner notified. Status={p_resp.status_code}, Response={p_resp.text}")
            except Exception as e:
                logger.error(f"Failed to notify Partner: {e}, Payload={partner_payload}")

        return Response({"status": "ok"})
            



class InitiateCardPayment(APIView):
    def post(self, request):
        try:
            data = request.data

            amount = float(data["price"])
            currency = data["currency"]

            transaction_uuid = str(uuid.uuid4())
            reference_number = f"EXO-{int(datetime.datetime.now().timestamp())}-{data['user_id']}"

            # Core CyberSource fields
            fields = {
                "access_key": settings.CYBERSOURCE_ACCESS_KEY,
                "profile_id": settings.CYBERSOURCE_PROFILE_ID,
                "transaction_uuid": transaction_uuid,
                "signed_field_names": (
                    "access_key,profile_id,transaction_uuid,"
                    "signed_field_names,unsigned_field_names,"
                    "amount,currency,reference_number,transaction_type,"
                    "signed_date_time,locale,"
                    "bill_to_forename,bill_to_surname,"
                    "bill_to_address_line1,bill_to_address_city,bill_to_address_country,"
                    "bill_to_email,bill_to_phone"
                ),
                "unsigned_field_names": "",
                "signed_date_time": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "locale": "en",
                "transaction_type": "sale",
                "reference_number": reference_number,
                "amount": str(amount),
                "currency": currency,
                # --- Hardcoded billing info for TEST ---
                "bill_to_forename": "John",
                "bill_to_surname": "Doe",
                "bill_to_address_line1": "123 Test Street",
                "bill_to_address_city": "Nairobi",
                "bill_to_address_country": "KE",
                "bill_to_email": "testuser@example.com",
                "bill_to_phone": "254700000000",
            }
            fields["signature"] = sign_fields(fields, settings.CYBERSOURCE_SECRET_KEY)


            # Lookup product/platform safely (optional)
            platform = Platform.objects.filter(id=data.get("platform_id")).first() if data.get("platform_id") else None
            product = Product.objects.filter(id=data.get("product_id")).first() if data.get("product_id") else None

            payment = Payment.objects.create(
                laravel_payment_id=data.get("payment_id"),
                user_id=data["user_id"],
                platform=platform,
                product=product,
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
                "cybersource_url": settings.CYBERSOURCE_API_URL,
                "payment_data": fields
            })

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

class OrganizationViewSet(viewsets.ModelViewSet):
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer

            
