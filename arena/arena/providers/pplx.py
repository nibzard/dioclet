# ABOUTME: Perplexity Decider seat provider on the System One decisions path.
# ABOUTME: No trailing slash on the endpoint; long timeout per vendor guidance.

import os

from arena.providers import ProviderError
from arena.providers.systemone import SystemOneProvider

DEFAULT_MODEL = "pplx-decider-v1.3"
PRICING = {
    "pplx-decider-v1.3": 0.02,
    "pplx-decider-v1.2": 0.02,
    "pplx-decider-flash-v1.3": 0.01,
    "pplx-decider-flash-v1.2": 0.01,
    "*": 0.02,
}
TIMEOUT_S = 65.0
BASE_URL = "https://api.perplexity.ai/v1/decisions"


class PplxProvider(SystemOneProvider):

    def _extra_usage(self, response) -> dict:
        request_id = response.headers.get("x-request-id")
        return {"request_id": request_id} if request_id else {}


def build(model: str | None = None, http_client=None) -> PplxProvider:
    api_key = os.environ.get("PERPLEXITY_API_KEY")
    if not api_key:
        raise ProviderError(
            "pplx needs PERPLEXITY_API_KEY in the environment")
    return PplxProvider(
        name="pplx",
        base_url=BASE_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        model=model or DEFAULT_MODEL,
        pricing=PRICING,
        timeout_s=TIMEOUT_S,
        http_client=http_client,
    )
