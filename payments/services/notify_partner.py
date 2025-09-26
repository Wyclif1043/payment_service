import requests
import logging

logger = logging.getLogger(__name__)

class PartnerNotifier:
    def __init__(self, base_url):
        self.base_url = base_url

    def notify(self, org_code, amount):
        payload = {
            "Org_Code": org_code,
            "Amount": str(amount),
        }

        try:
            resp = requests.post(self.base_url, json=payload, timeout=10)
            if resp.status_code == 200:
                logger.info(f"Partner notified successfully: {payload}")
                return True, resp.json() if resp.headers.get("Content-Type") == "application/json" else resp.text
            else:
                logger.error(f"Partner API failed. Code={resp.status_code}, Body={resp.text}, Payload={payload}")
                return False, resp.text
        except Exception as e:
            logger.error(f"🔥 Partner notification failed: {e}, Payload={payload}")
            return False, str(e)
