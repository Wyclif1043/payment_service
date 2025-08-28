import hmac, hashlib, base64

def sign_fields(params: dict, secret_key: str) -> str:
    if "signed_field_names" not in params:
        raise ValueError("signed_field_names is required")

    signed_fields = params["signed_field_names"].split(",")
    data_to_sign = []

    for field in signed_fields:
        field = field.strip()
        if field in params:
            data_to_sign.append(f"{field}={params[field]}")

    data_string = ",".join(data_to_sign)
    signature = hmac.new(
        secret_key.encode("utf-8"),
        data_string.encode("utf-8"),
        hashlib.sha256
    ).digest()
    return base64.b64encode(signature).decode("utf-8")