# mpesa helper (paste near top of your views module)
import base64
import time
from django.conf import settings
import json
import uuid
import datetime
import requests


def get_mpesa_oauth_token(org_config):
    """
    Get Daraja access token for the org_config (uses consumer key/secret stored per org).
    Returns token or raises Exception on failure.
    """
    env = org_config.mpesa_environment or "sandbox"
    oauth_url = settings.MPESA_SANDBOX_OAUTH if env == "sandbox" else settings.MPESA_PROD_OAUTH

    consumer_key = org_config.mpesa_consumer_key
    consumer_secret = org_config.mpesa_consumer_secret

    resp = requests.get(oauth_url, auth=(consumer_key, consumer_secret))
    if resp.status_code != 200:
        raise Exception(f"MPESA oauth failed: {resp.status_code} {resp.text}")
    return resp.json().get("access_token")


def lipa_na_mpesa_stk_push(org_config, token, amount, phone, account_reference, callback_url, description="Payment"):
    """
    Initiate STK Push via Daraja.
    Returns the response JSON (or raises).
    """
    env = org_config.mpesa_environment or "sandbox"
    stk_url = settings.MPESA_SANDBOX_STK if env == "sandbox" else settings.MPESA_PROD_STK

    shortcode = org_config.mpesa_shortcode
    passkey = org_config.mpesa_passkey

    # Timestamp format: YYYYMMDDHHMMSS
    timestamp = time.strftime("%Y%m%d%H%M%S", time.gmtime())

    # Password = base64encode(shortcode + passkey + timestamp)
    raw_password = f"{shortcode}{passkey}{timestamp}"
    password = base64.b64encode(raw_password.encode()).decode()

    payload = {
        "BusinessShortCode": shortcode,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": int(float(amount)),
        "PartyA": phone,              # customer MSISDN format 2547XXXXXXXX
        "PartyB": shortcode,
        "PhoneNumber": phone,
        "CallBackURL": callback_url,
        "AccountReference": account_reference,
        "TransactionDesc": description
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    resp = requests.post(stk_url, json=payload, headers=headers, timeout=30)
    # Return json / raise
    if resp.status_code not in (200, 201):
        raise Exception(f"STK push failed: {resp.status_code} {resp.text}")
    return resp.json()
