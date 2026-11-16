# ABOUTME: Fixture tests for the remote providers at the HTTP boundary.
# ABOUTME: Every double lives here; production providers take only real clients.

import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from arena import engine_adapter
from arena.providers import (InvalidAnswerError, ProviderError,
                             RefusalError, TransportError, TurnView)
from arena.providers import clef, jev, openai_decisions, pplx
from arena.rules_loader import load_rules_strict

RULES_PATH = Path(__file__).resolve().parents[1] / "rules" / "v0102.json"


@pytest.fixture(scope="module")
def view():
    rules = load_rules_strict(RULES_PATH)
    state = engine_adapter.new_game(rules, 42, "provider-tests")
    obs = engine_adapter.observe(state)
    projection = engine_adapter.projection(obs, rules)
    candidates, _ = engine_adapter.candidates(obs, rules)
    return TurnView(observation=obs, projection=projection,
                    candidates=candidates, rules=rules)


def _payload(choice, model="any", probabilities=None,
             input_tokens=1000, output_tokens=7, answer_type="choice"):
    answer = {"type": answer_type, "choice": choice, "confidence": 0.6}
    if probabilities is not None:
        answer["probabilities"] = probabilities
    return {"model": model, "answers": {"best_action": answer},
            "usage": {"input_tokens": input_tokens,
                      "output_tokens": output_tokens}}


def _capture_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def _prob_pair(view):
    ids = [c["action_id"] for c in view.candidates]
    if len(ids) == 1:
        return {ids[0]: 1.0}
    return {ids[0]: 0.62, ids[1]: 0.38}


class TestJev:
    def test_request_shape_and_decision(self, view, monkeypatch):
        monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
        captured = {}

        def handler(request):
            captured["url"] = str(request.url)
            captured["auth"] = request.headers["authorization"]
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json=_payload(
                view.candidates[0]["action_id"], model="jev-latest",
                probabilities=_prob_pair(view)))

        provider = jev.build(http_client=_capture_client(handler))
        decision = provider.decide(view)
        assert captured["url"] == "https://api.typesafe.ai/v1/systemone"
        assert captured["auth"] == "Bearer test-key"
        body = captured["body"]
        assert body["model"] == "jev-latest"
        assert body["state"] == view.projection
        question = body["questions"]["best_action"]
        assert question["type"] == "choice"
        assert set(question["criteria"]) == \
            {c["action_id"] for c in view.candidates}
        assert decision.action_id == view.candidates[0]["action_id"]
        assert decision.probabilities is not None
        assert decision.probabilities[view.candidates[0]["action_id"]] \
            == pytest.approx(0.62)
        assert decision.usage["input_tokens"] == 1000
        assert decision.cost_usd == pytest.approx(1000 / 1e6 * 0.042)
        assert decision.reason == "jev_choice"

    def test_missing_key_is_a_clear_error(self, monkeypatch):
        monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
        with pytest.raises(ProviderError, match="TYPESAFE_API_KEY"):
            jev.build()

    @pytest.mark.parametrize("status", [429, 529, 500, 503])
    def test_transient_status_is_transport_error(self, view, monkeypatch,
                                                 status):
        monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")

        def handler(request):
            return httpx.Response(status, text="overloaded")

        provider = jev.build(http_client=_capture_client(handler))
        with pytest.raises(TransportError, match=str(status)):
            provider.decide(view)

    @pytest.mark.parametrize("status", [400, 401, 422])
    def test_permanent_status_is_provider_error(self, view, monkeypatch,
                                                status):
        monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")

        def handler(request):
            return httpx.Response(status, text='{"error":"bad request"}')

        provider = jev.build(http_client=_capture_client(handler))
        with pytest.raises(ProviderError, match=str(status)):
            provider.decide(view)


class TestSystemOneCore:
    @pytest.fixture()
    def provider(self, view, monkeypatch):
        monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
        return jev.build(http_client=_capture_client(
            lambda request: httpx.Response(
                200, json=_payload(view.candidates[0]["action_id"]))))

    def test_illegal_choice_is_invalid(self, view, provider):
        def handler(request):
            return httpx.Response(200, json=_payload("a9999"))
        provider._client = _capture_client(handler)
        with pytest.raises(InvalidAnswerError, match="a9999"):
            provider.decide(view)

    def test_non_choice_answer_is_invalid(self, view, provider):
        def handler(request):
            return httpx.Response(200, json=_payload(
                "x", answer_type="ranking"))
        provider._client = _capture_client(handler)
        with pytest.raises(InvalidAnswerError, match="ranking"):
            provider.decide(view)

    def test_missing_answers_is_invalid(self, view, provider):
        def handler(request):
            return httpx.Response(200, json={"model": "jev-latest"})
        provider._client = _capture_client(handler)
        with pytest.raises(InvalidAnswerError, match="best_action"):
            provider.decide(view)

    def test_non_json_is_invalid(self, view, provider):
        def handler(request):
            return httpx.Response(200, text="<html>gateway</html>")
        provider._client = _capture_client(handler)
        with pytest.raises(InvalidAnswerError, match="not JSON"):
            provider.decide(view)

    def test_timeout_is_transport_error(self, view, monkeypatch):
        monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")

        def handler(request):
            raise httpx.ConnectTimeout("connect timed out")

        provider = jev.build(http_client=_capture_client(handler))
        with pytest.raises(TransportError, match="timed out"):
            provider.decide(view)

    def test_probabilities_with_unknown_id_are_dropped(self, view,
                                                       monkeypatch):
        monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
        pair = _prob_pair(view)
        poisoned = dict(pair)
        poisoned["not_an_action"] = 0.01

        def handler(request):
            return httpx.Response(200, json=_payload(
                view.candidates[0]["action_id"], probabilities=poisoned))

        provider = jev.build(http_client=_capture_client(handler))
        assert provider.decide(view).probabilities is None

    def test_probabilities_out_of_range_are_dropped(self, view, monkeypatch):
        monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
        ids = [c["action_id"] for c in view.candidates]
        bad = {ids[0]: 1.5} if len(ids) == 1 else {ids[0]: 0.0, ids[1]: 1.3}

        def handler(request):
            return httpx.Response(200, json=_payload(
                ids[0], probabilities=bad))

        provider = jev.build(http_client=_capture_client(handler))
        assert provider.decide(view).probabilities is None


class TestClef:
    @pytest.fixture(autouse=True)
    def env(self, monkeypatch):
        monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "cf-token")
        monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct-123")

    def test_url_account_interpolation_and_default_model(self, view):
        captured = {}

        def handler(request):
            captured["url"] = str(request.url)
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json=_payload(
                view.candidates[0]["action_id"], model="clef-flash"))

        provider = clef.build(http_client=_capture_client(handler))
        decision = provider.decide(view)
        assert captured["url"] == ("https://api.cloudflare.com/client/v4/"
                                   "accounts/acct-123/ai/run/"
                                   "@cf/cloudflare/clef-flash")
        assert captured["body"]["model"] == "clef-flash"
        assert decision.cost_usd == pytest.approx(1000 / 1e6 * 0.038)

    def test_prefixed_model_is_normalized_and_priced_as_full_clef(self,
                                                                  view):
        captured = {}

        def handler(request):
            captured["url"] = str(request.url)
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json=_payload(
                view.candidates[0]["action_id"], model="clef"))

        provider = clef.build(model="@cf/cloudflare/clef",
                              http_client=_capture_client(handler))
        decision = provider.decide(view)
        assert captured["url"].endswith("/ai/run/@cf/cloudflare/clef")
        assert captured["body"]["model"] == "clef"
        assert decision.cost_usd == pytest.approx(1000 / 1e6 * 0.24)

    def test_missing_account_id_is_a_clear_error(self, monkeypatch):
        monkeypatch.delenv("CLOUDFLARE_ACCOUNT_ID", raising=False)
        with pytest.raises(ProviderError, match="CLOUDFLARE_ACCOUNT_ID"):
            clef.build()

    def test_missing_token_is_a_clear_error(self, monkeypatch):
        monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)
        with pytest.raises(ProviderError, match="CLOUDFLARE_API_TOKEN"):
            clef.build()


class TestPplx:
    @pytest.fixture(autouse=True)
    def env(self, monkeypatch):
        monkeypatch.setenv("PERPLEXITY_API_KEY", "pplx-key")

    def test_endpoint_has_no_trailing_slash_and_request_id_captured(self,
                                                                    view):
        captured = {}

        def handler(request):
            captured["url"] = str(request.url)
            captured["auth"] = request.headers["authorization"]
            return httpx.Response(200, json=_payload(
                view.candidates[0]["action_id"], model="pplx-decider-v1.3"),
                headers={"x-request-id": "req-42"})

        provider = pplx.build(http_client=_capture_client(handler))
        decision = provider.decide(view)
        assert captured["url"] == "https://api.perplexity.ai/v1/decisions"
        assert captured["auth"] == "Bearer pplx-key"
        assert decision.usage["request_id"] == "req-42"
        assert decision.cost_usd == pytest.approx(1000 / 1e6 * 0.02)

    def test_flash_model_pricing(self, view):
        def handler(request):
            return httpx.Response(200, json=_payload(
                view.candidates[0]["action_id"],
                model="pplx-decider-flash-v1.3"))

        provider = pplx.build(model="pplx-decider-flash-v1.3",
                              http_client=_capture_client(handler))
        assert provider.decide(view).cost_usd == \
            pytest.approx(1000 / 1e6 * 0.01)

    def test_missing_key_is_a_clear_error(self, monkeypatch):
        monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
        with pytest.raises(ProviderError, match="PERPLEXITY_API_KEY"):
            pplx.build()


class _FakeAnswer:
    def __init__(self, answer_type="choice", name="best_action",
                 choice=None, probabilities=None):
        self.type = answer_type
        self.name = name
        self.choice = choice
        self.probabilities = probabilities


class _FakeResponse:
    def __init__(self, answers, usage=None, model="gpt-6-luna", id="req_1"):
        self.answers = answers
        self.usage = usage
        self.model = model
        self.id = id


class _FakeClient:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []
        self.decisions = SimpleNamespace(create=self._create)

    def with_options(self, **kwargs):
        self.options = kwargs
        return self

    def _create(self, **request):
        self.calls.append(request)
        if self.error is not None:
            raise self.error
        return self.response


def _usage(input_tokens=1000, output_tokens=5):
    return SimpleNamespace(
        input_tokens=input_tokens, output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        input_tokens_details=SimpleNamespace(cached_tokens=0,
                                             cache_write_tokens=0))


class TestOpenAI:
    @pytest.fixture(autouse=True)
    def env(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "oa-key")

    def _provider(self, client):
        return openai_decisions.build(client=client)

    def test_request_shape_and_decision(self, view):
        ids = [c["action_id"] for c in view.candidates]
        pair = [{"value": ids[0], "probability": 0.7},
                {"value": ids[1], "probability": 0.3}] \
            if len(ids) > 1 else [{"value": ids[0], "probability": 1.0}]
        client = _FakeClient(_FakeResponse(
            [_FakeAnswer(choice=ids[0], probabilities=pair)], usage=_usage()))
        decision = self._provider(client).decide(view)
        request = client.calls[0]
        assert client.options["max_retries"] == 0
        assert request["model"] == "gpt-6-luna"
        content = request["input"][0]["content"]
        assert content[0] == {"type": "input_text", "text":
                              openai_decisions.INTRO_TEXT}
        evidence = content[1]["data"]
        assert evidence["candidate_features"][0]["action_id"] == ids[0]
        question = request["questions"][0]
        assert question["name"] == "best_action"
        assert [c["value"] for c in question["choices"]] == ids
        assert decision.action_id == ids[0]
        assert decision.probabilities == {ids[0]: 0.7} | \
            ({ids[1]: 0.3} if len(ids) > 1 else {})
        assert decision.usage["input_tokens"] == 1000
        assert decision.cost_usd == pytest.approx(1000 / 1e6 * 0.10)
        assert decision.reason == "openai_decisions_choice"

    def test_refusal(self, view):
        client = _FakeClient(_FakeResponse([_FakeAnswer(answer_type="refusal")]))
        with pytest.raises(RefusalError):
            self._provider(client).decide(view)

    def test_illegal_choice(self, view):
        client = _FakeClient(_FakeResponse([_FakeAnswer(choice="nope")]))
        with pytest.raises(InvalidAnswerError, match="nope"):
            self._provider(client).decide(view)

    def test_empty_answers(self, view):
        client = _FakeClient(_FakeResponse([]))
        with pytest.raises(InvalidAnswerError, match="empty"):
            self._provider(client).decide(view)

    def test_transport_failure_wraps_sdk_error(self, view):
        client = _FakeClient(error=RuntimeError("connection reset"))
        with pytest.raises(TransportError, match="connection reset"):
            self._provider(client).decide(view)

    def test_missing_key_is_a_clear_error(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with pytest.raises(ProviderError, match="OPENAI_API_KEY"):
            openai_decisions.build(client=object())
