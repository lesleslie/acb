from httpx import AsyncClient
from pydantic import BaseModel
from . import GoogleSettings
from ...actions.log import logger


class RecaptchaSettings(GoogleSettings):
    production_key = ac.secrets.recaptcha_production_key
    dev_key = ac.secrets.recaptcha_dev_key
    threshold = 0.5 if deployed else 0.1


class Recaptcha(BaseModel):
    headers = {
        "Content-type": "application/x-www-form-urlencoded",
        "Accept": "text/plain",
    }

    async def init(self):
        logger.info("Recaptcha initialized.")

    # def request(payload):
    #     params = urllib.parse.urlencode(payload)
    #     conn = http.client.HTTPSConnection("www.google.com")
    #     conn.request("POST", "/recaptcha/api/siteverify", params, headers)
    #     return json.loads(conn.getresponse().read())
    #
    async def is_a_human(
        self,
        secret_key,
        response_token,
        action=None,
        threshold=float(ac.google.recaptcha.threshold),
    ):
        payload = {"secret": secret_key, "response": response_token}
        async with AsyncClient() as client:
            resp = await client.post(
                "https://www.google.com/recaptcha/api/siteverify",
                params=payload,
                headers=self.headers,
            )
        response = resp.json()
        if not response["success"]:
            logger.warning("Failed communication")
            return False, 101
        elif response["score"] >= threshold:
            if action and response.get("action", None):
                if action != response["action"]:
                    logger.warning(
                        f"Bad action name: sent {action}, expected {response['action']}"
                    )
                    return False, 102
            logger.debug("Recaptcha verified human.")
            return True, 100
        else:
            logger.warning(
                f"Recaptcha threshold failed: got {response['score']}, expected >"
                f" {threshold}"
            )
            return False, 103

    async def recaptcha3(
        self,
        secret_key,
        response_token,
        action=None,
        threshold=float(ac.google.recaptcha.threshold),
    ):
        if not ac.app.is_deployed or ac.debug.production:
            threshold = 0.01
        ok, _ = await self.is_a_human(secret_key, response_token, action, threshold)
        return ok


recaptcha = Recaptcha()
