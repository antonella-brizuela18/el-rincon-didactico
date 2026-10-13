"""Checkout Pro adapter. No payment status is trusted from the browser return."""
import hashlib
import hmac
import json
import re
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import current_app


class PaymentError(Exception):
    pass


def mp_configured():
    config = current_app.config
    return bool(config.get("MP_ACCESS_TOKEN") and config.get("MP_WEBHOOK_SECRET") and
                config.get("MP_COLLECTOR_ID") and config.get("SITE_URL", "").startswith("https://"))


def mp_request(method, path, payload=None, key=None):
    headers = {"Authorization":"Bearer "+current_app.config["MP_ACCESS_TOKEN"], "Content-Type":"application/json"}
    if key:
        headers["X-Idempotency-Key"] = key
    body = json.dumps(payload).encode() if payload is not None else None
    request = Request("https://api.mercadopago.com"+path, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=15) as response:
            return json.load(response)
    except (HTTPError, URLError, TimeoutError, ValueError) as error:
        # Neither response bodies nor access tokens are logged.
        raise PaymentError() from error


def valid_signature(payment_id, request_id, signature):
    if not re.fullmatch(r"[0-9]{1,30}", payment_id) or not request_id or len(request_id)>200:
        return False
    try:
        values = dict(part.strip().split("=", 1) for part in signature.split(","))
        timestamp = values["ts"]
        epoch = int(timestamp)
        if epoch>10**12:
            epoch /= 1000
        if abs(time.time()-epoch)>300:
            return False
        manifest = f"id:{payment_id};request-id:{request_id};ts:{timestamp};"
        expected = hmac.new(current_app.config["MP_WEBHOOK_SECRET"].encode(), manifest.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, values["v1"])
    except (ValueError, KeyError):
        return False
