"""Gateway-to-Auth REST adapter. No credential store, JWT key or Redis client here."""
import requests

from back.lab3.common import DomainError


class AuthAPIClient:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip("/")

    def request(self, method, path, token=None, body=None):
        headers = {"Authorization": "Bearer " + token} if token else {}
        try:
            response = requests.request(method, self.base_url + path, headers=headers,
                                        json=body, timeout=6)
            data = response.json()
        except (requests.RequestException, ValueError):
            raise DomainError("DEPENDENCY_UNAVAILABLE", "Auth Service недоступен") from None
        if response.status_code >= 400:
            raise DomainError(data.get("code", "AUTH_ERROR"),
                              data.get("message", "Операция Auth Service отклонена"))
        return data

    def sign_in(self, login, password):
        return self.request("POST", "/login", body={"login": login, "password": password})

    def validate(self, token):
        return self.request("GET", "/validate", token=token)

    def sign_out(self, token):
        return self.request("POST", "/logout", token=token)["signedOut"]

    def register_staff(self, token, values):
        return self.request("POST", "/staff", token=token, body=values)

    def block_staff(self, token, user_id, key):
        return self.request("POST", f"/staff/{user_id}/block", token=token,
                            body={"idempotencyKey": key})

    def change_staff_role(self, token, user_id, role, key):
        return self.request("POST", f"/staff/{user_id}/role", token=token,
                            body={"roleCode": role, "idempotencyKey": key})
