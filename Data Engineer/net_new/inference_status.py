"""Read candidate status without loading documents or running inference."""

from urllib.parse import urlparse

import httpx

from .pipeline import inference_connection


def account_status() -> dict:
    connection = inference_connection("litellm")
    base = connection["base_url"].rstrip("/")
    if urlparse(base).path.rstrip("/") != "/v1":
        raise ValueError("ARGUS_INFERENCE_URL must end with /v1")
    try:
        with httpx.Client(timeout=20, follow_redirects=False) as client:
            response = client.get(
                base + "/account", headers={"Authorization": "Bearer " + connection["api_key"]}
            )
    except httpx.HTTPError:
        raise ValueError(
            "Inference status unavailable; check the endpoint and connection"
        ) from None
    if response.status_code != 200:
        raise ValueError(
            f"Inference status HTTP {response.status_code}; check key access or contact the operator"
        )
    result = response.json()
    if (
        not isinstance(result, dict)
        or not {"models", "budget_usd", "spent_usd", "available_usd", "expires_at"} <= result.keys()
    ):
        raise ValueError("Inference status response is incomplete")
    return result
