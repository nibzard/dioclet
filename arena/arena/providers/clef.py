# ABOUTME: Cloudflare Clef seat provider: System One on the Workers AI run path.
# ABOUTME: The URL keeps the @cf/cloudflare/ model prefix; the body model is bare.

import os

from arena.providers import ProviderError
from arena.providers.systemone import SystemOneProvider

DEFAULT_MODEL = "clef-flash"
PRICING = {"clef": 0.24, "clef-flash": 0.038, "*": 0.24}
TIMEOUT_S = 30.0
BASE_URL = ("https://api.cloudflare.com/client/v4/accounts/"
            "{account_id}/ai/run/@cf/cloudflare/{model}")


def _bare_model(model: str) -> str:
    prefix = "@cf/cloudflare/"
    if model.startswith(prefix):
        return model[len(prefix):]
    return model


def build(model: str | None = None, http_client=None) -> SystemOneProvider:
    model = _bare_model(model or DEFAULT_MODEL)
    token = os.environ.get("CLOUDFLARE_API_TOKEN")
    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    missing = [name for name, value in (
        ("CLOUDFLARE_API_TOKEN", token),
        ("CLOUDFLARE_ACCOUNT_ID", account_id)) if not value]
    if missing:
        raise ProviderError(
            f"clef needs {' and '.join(missing)} in the environment")
    return SystemOneProvider(
        name="clef",
        base_url=BASE_URL.format(account_id=account_id, model=model),
        headers={"Authorization": f"Bearer {token}"},
        model=model,
        pricing=PRICING,
        timeout_s=TIMEOUT_S,
        http_client=http_client,
    )
