# ABOUTME: TypeSafe Jev seat provider on the System One REST endpoint.
# ABOUTME: Pricing and models per docs.typesafe.ai; one key, one question.

import os

from arena.providers import ProviderError
from arena.providers.systemone import SystemOneProvider

DEFAULT_MODEL = "jev-latest"
PRICING = {"*": 0.042}
TIMEOUT_S = 10.0
BASE_URL = "https://api.typesafe.ai/v1/systemone"


def build(model: str | None = None, http_client=None) -> SystemOneProvider:
    api_key = os.environ.get("TYPESAFE_API_KEY")
    if not api_key:
        raise ProviderError("jev needs TYPESAFE_API_KEY in the environment")
    return SystemOneProvider(
        name="jev",
        base_url=BASE_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        model=model or DEFAULT_MODEL,
        pricing=PRICING,
        timeout_s=TIMEOUT_S,
        http_client=http_client,
    )
