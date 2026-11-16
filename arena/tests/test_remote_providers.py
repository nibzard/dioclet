# ABOUTME: Fixture tests for the remote providers at the HTTP boundary.
# ABOUTME: Every double lives here; production providers take only real clients.

import dataclasses
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import pytest

from arena import engine_adapter
from arena.evidence import EVIDENCE_SCHEMA, build_evidence
from arena.providers import (InvalidAnswerError, ProviderError,
                             RefusalError, TransportError, TurnView)
from arena.providers import (REMOTE_PROVIDERS, REQUIRED_ENV, clef, gateway,
                             jev, openai_decisions, pplx)
from arena.providers.openai_decisions import OpenAIDecisions
from arena.providers.systemone import SystemOneProvider
from arena.prompt import INTRO
from arena.rules_loader import load_rules_strict
from candidate_actions import claim_rule_text

RULES_PATH = Path(__file__).resolve().parents[2] / "rules" / "imperial-rivals-v0.10.2.json"


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
        assert body["state"] == build_evidence(view)
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


def _workers_ai(result, success=True, errors=()):
    """Workers AI wraps every model result in this envelope."""
    return {"result": result, "success": success, "errors": list(errors),
            "messages": []}


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
            return httpx.Response(200, json=_workers_ai(_payload(
                view.candidates[0]["action_id"], model="clef-flash")))

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
            return httpx.Response(200, json=_workers_ai(_payload(
                view.candidates[0]["action_id"], model="clef")))

        provider = clef.build(model="@cf/cloudflare/clef",
                              http_client=_capture_client(handler))
        decision = provider.decide(view)
        assert captured["url"].endswith("/ai/run/@cf/cloudflare/clef")
        assert captured["body"]["model"] == "clef"
        assert decision.cost_usd == pytest.approx(1000 / 1e6 * 0.24)

    def test_unsuccessful_envelope_reports_errors(self, view):
        def handler(request):
            return httpx.Response(200, json=_workers_ai(
                None, success=False,
                errors=[{"code": 5007, "message": "model unavailable"}]))

        provider = clef.build(http_client=_capture_client(handler))
        with pytest.raises(InvalidAnswerError, match="model unavailable"):
            provider.decide(view)

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
        assert content[0] == {"type": "input_text", "text": INTRO}
        evidence = content[1]["data"]
        assert evidence == build_evidence(view)
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


class TestGateway:
    @pytest.fixture(autouse=True)
    def env(self, monkeypatch):
        monkeypatch.setenv("AI_GATEWAY_API_KEY", "gw-key")

    def _decide(self, view, model, input_tokens=1000):
        ids = [c["action_id"] for c in view.candidates]
        client = _FakeClient(_FakeResponse(
            [_FakeAnswer(choice=ids[0])], usage=_usage(input_tokens),
            model=model))
        decision = gateway.build(model, client=client).decide(view)
        return client, decision

    def test_registered_with_its_key(self):
        assert "gateway" in REMOTE_PROVIDERS
        assert REQUIRED_ENV["gateway"] == ("AI_GATEWAY_API_KEY",)

    def test_request_uses_gateway_model_id(self, view):
        client, decision = self._decide(view, "typesafe-ai/jev")
        assert client.calls[0]["model"] == "typesafe-ai/jev"
        assert client.calls[0]["questions"][0]["name"] == "best_action"
        assert decision.reason == "gateway_decisions_choice"
        assert decision.cost_usd == pytest.approx(1000 / 1e6 * 0.04)

    def test_default_model_is_priced(self):
        assert gateway.DEFAULT_MODEL in gateway.PRICING

    def test_per_request_fee_is_added(self, view):
        _, decision = self._decide(view, "perplexity/pplx-decider-flash-v1.3")
        assert decision.cost_usd == pytest.approx(1000 / 1e6 * 0.01 + 0.001)

    def test_unpriced_model_is_rejected(self):
        with pytest.raises(ProviderError, match="no price"):
            gateway.build("acme/unknown-decider", client=object())

    def test_missing_key_is_a_clear_error(self, monkeypatch):
        monkeypatch.delenv("AI_GATEWAY_API_KEY", raising=False)
        with pytest.raises(ProviderError, match="AI_GATEWAY_API_KEY"):
            gateway.build(client=object())

    def test_real_client_points_at_gateway(self, monkeypatch):
        import openai
        seen = {}
        monkeypatch.setattr(openai, "OpenAI",
                            lambda **kwargs: seen.update(kwargs) or object())
        gateway.build()
        assert seen == {"base_url": "https://ai-gateway.vercel.sh/v1",
                        "api_key": "gw-key"}


class TestExchangeCapture:
    """Every adapter returns what it sent and what it got, for training."""

    @pytest.fixture(autouse=True)
    def env(self, monkeypatch):
        monkeypatch.setenv("TYPESAFE_API_KEY", "ts-key")
        monkeypatch.setenv("OPENAI_API_KEY", "oa-key")
        monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "cf-token")
        monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct-123")

    def test_systemone_success_keeps_request_raw_body_and_confidence(
            self, view):
        payload = _payload(view.candidates[0]["action_id"])
        provider = jev.build(http_client=_capture_client(
            lambda request: httpx.Response(200, json=payload)))
        decision = provider.decide(view)
        assert decision.exchange["request"] == provider.build_request(view)
        assert decision.exchange["response"] == {"status_code": 200,
                                                 "body": payload}
        assert decision.confidence == 0.6
        assert "ts-key" not in json.dumps(decision.exchange)

    def test_clef_keeps_the_whole_envelope(self, view):
        envelope = _workers_ai(_payload(view.candidates[0]["action_id"]))
        provider = clef.build(http_client=_capture_client(
            lambda request: httpx.Response(200, json=envelope)))
        assert provider.decide(view).exchange["response"]["body"] == envelope

    def test_systemone_invalid_answer_carries_exchange(self, view):
        payload = _payload("nope")
        provider = jev.build(http_client=_capture_client(
            lambda request: httpx.Response(200, json=payload)))
        with pytest.raises(InvalidAnswerError) as info:
            provider.decide(view)
        assert info.value.exchange["response"]["body"] == payload

    def test_systemone_http_error_carries_status_and_body(self, view):
        provider = jev.build(http_client=_capture_client(
            lambda request: httpx.Response(400, text="bad request")))
        with pytest.raises(ProviderError) as info:
            provider.decide(view)
        assert info.value.exchange["response"] == {"status_code": 400,
                                                   "body": "bad request"}
        assert info.value.exchange["request"]["model"] == "jev-latest"

    def test_openai_success_keeps_request_dump_and_confidence(self, view):
        ids = [c["action_id"] for c in view.candidates]
        answer = _FakeAnswer(choice=ids[0])
        answer.confidence = 0.8
        client = _FakeClient(_FakeResponse([answer], usage=_usage()))
        decision = openai_decisions.build(client=client).decide(view)
        assert decision.exchange["request"] == client.calls[0]
        body = decision.exchange["response"]["body"]
        assert body["answers"][0]["choice"] == ids[0]
        assert body["usage"]["input_tokens"] == 1000
        assert decision.confidence == 0.8

    def test_openai_transport_error_carries_request(self, view):
        client = _FakeClient(error=RuntimeError("reset"))
        with pytest.raises(TransportError) as info:
            openai_decisions.build(client=client).decide(view)
        assert info.value.exchange["request"]["model"] == "gpt-6-luna"
        assert info.value.exchange["response"] is None


def _proclaimed_view(rules):
    """A turn where a live claim is pending and a cancelling duel is legal."""
    engine = engine_adapter.engine
    state = engine_adapter.new_game(rules, 7, "evidence-parity")
    state.update(turn_order=list(engine.IDS), round_start=0,
                 turn_index=0, active_player="P0")
    state["phase"] = 2
    state["players"]["P0"].update(pos=[9, 6], support=["army", "elites"])
    state["players"]["P1"].update(pos=[8, 6], prestige=1)
    state["current_roll"], state["current_dice"] = 6, [3, 3]
    proclaim = next(a["action_id"] for a in engine.legal_actions(state)
                    if a["kind"] == "proclaim")
    # The proclaim ends P0's turn; P1's turn start rolls two dice.
    with patch.object(engine, "_die", side_effect=[3, 3]):
        engine_adapter.apply(state, proclaim)
    obs = engine_adapter.observe(state)
    view = TurnView(observation=obs,
                    projection=engine_adapter.projection(obs, rules),
                    candidates=engine_adapter.candidates(obs, rules)[0],
                    rules=rules)
    assert view.projection["pending_claim"]
    assert any(c["kind"] == "duel" for c in view.candidates)
    return view


class TestEvidenceParity:
    """Every adapter embeds exactly build_evidence(view) in its request.

    A failure here means an adapter added, removed, or reworded game
    data inside its envelope.
    """

    @pytest.fixture(autouse=True)
    def env(self, monkeypatch):
        monkeypatch.setenv("TYPESAFE_API_KEY", "ts-key")
        monkeypatch.setenv("OPENAI_API_KEY", "oa-key")
        monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "cf-token")
        monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct-123")
        monkeypatch.setenv("PERPLEXITY_API_KEY", "pplx-key")
        monkeypatch.setenv("AI_GATEWAY_API_KEY", "gw-key")

    def _adapters(self):
        """One provider object per family: jev, clef, pplx, openai, gateway."""
        return [
            ("clef", clef.build()),
            ("gateway", gateway.build("nace-ai/drex-v2.0", client=object())),
            ("jev", jev.build()),
            ("openai", openai_decisions.build(client=object())),
            ("pplx", pplx.build()),
        ]

    @staticmethod
    def _extract(provider, view):
        request = provider.build_request(view)
        if isinstance(provider, SystemOneProvider):
            return request["state"]
        return request["input"][0]["content"][1]["data"]

    def _assert_identical(self, name, provider, view):
        expected = build_evidence(view)
        got = self._extract(provider, view)
        assert got == expected, name
        assert json.dumps(got, sort_keys=True) \
            == json.dumps(expected, sort_keys=True), name

    def test_succession_turn_matches_every_adapter(self, view):
        for name, provider in self._adapters():
            self._assert_identical(name, provider, view)

    def test_pending_claim_turn_matches_every_adapter(self):
        rules = load_rules_strict(RULES_PATH)
        view = _proclaimed_view(rules)
        for name, provider in self._adapters():
            self._assert_identical(name, provider, view)

    def test_legacy_classic_branch_matches_every_adapter(self, view):
        projection = {key: value for key, value in view.projection.items()
                      if key != "gameplay_mode"}
        classic = dataclasses.replace(view, projection=projection)
        for name, provider in self._adapters():
            self._assert_identical(name, provider, classic)

    def test_evidence_holds_the_projection_and_four_public_keys(self, view):
        evidence = build_evidence(view)
        assert set(evidence) == {"schema", "projection", "candidates"}
        assert evidence["schema"] == EVIDENCE_SCHEMA
        assert evidence["projection"] == view.projection
        assert "rule_summary" in evidence["projection"]
        assert "rule_summary" not in evidence
        for shown, full in zip(evidence["candidates"], view.candidates):
            assert set(shown) == {"action_id", "kind", "description",
                                  "features"}
            assert shown["action_id"] == full["action_id"]


class TestProviderRuleText:
    """One sweep of every string a provider can see, against the rules."""

    PERISTYLE = [9, 6]
    NEAR_PERISTYLE = [8, 6]

    @classmethod
    def _view(cls, rules, proclaimed):
        engine = engine_adapter.engine
        state = engine_adapter.new_game(rules, 7, "rule-text")
        state.update(turn_order=list(engine.IDS), round_start=0,
                     turn_index=0, active_player="P0")
        state["phase"] = 2
        state["players"]["P0"].update(pos=list(cls.PERISTYLE),
                                      support=["army", "elites"])
        state["players"]["P1"].update(pos=list(cls.NEAR_PERISTYLE),
                                      prestige=1)
        state["current_roll"], state["current_dice"] = 6, [3, 3]
        if proclaimed:
            proclaim = next(a["action_id"] for a in engine.legal_actions(state)
                            if a["kind"] == "proclaim")
            # The proclaim ends P0's turn; P1's turn start rolls two dice.
            with patch.object(engine, "_die", side_effect=[3, 3]):
                engine_adapter.apply(state, proclaim)
        obs = engine_adapter.observe(state)
        projection = engine_adapter.projection(obs, rules)
        candidates, _ = engine_adapter.candidates(obs, rules)
        wanted = "duel" if proclaimed else "proclaim"
        assert any(c["kind"] == wanted for c in candidates)
        return TurnView(observation=obs, projection=projection,
                        candidates=candidates, rules=rules)

    @classmethod
    def _walk(cls, value):
        if isinstance(value, str):
            return [value]
        if isinstance(value, dict):
            found = []
            for key, item in value.items():
                found.extend(cls._walk(key))
                found.extend(cls._walk(item))
            return found
        if isinstance(value, (list, tuple)):
            found = []
            for item in value:
                found.extend(cls._walk(item))
            return found
        return []

    @classmethod
    def _provider_texts(cls, rules):
        views = (cls._view(rules, proclaimed=False),
                 cls._view(rules, proclaimed=True))
        providers = (
            SystemOneProvider("double", "http://double", {}, "double",
                              {"*": 0.0}, 1.0),
            OpenAIDecisions(client=object(), model="double"),
        )
        texts = []
        for view in views:
            for provider in providers:
                texts.extend(cls._walk(provider.build_request(view)))
        return texts

    def test_window_rules_reach_every_provider_string(self):
        rules = load_rules_strict(RULES_PATH)
        texts = self._provider_texts(rules)
        joined = " ".join(texts)
        expected = claim_rule_text(rules)
        assert expected in joined
        window = rules["succession"]["claim_window_rounds"]
        assert "Use the explicit deadline when a claim is pending." in joined
        # The value in any full-round wording is the rules value, verbatim.
        for text in texts:
            if "full round(s) uncancelled" in text:
                assert f"{window} full round(s) uncancelled" in text
        zero = claim_rule_text(
            {**rules, "succession":
                {**rules["succession"], "claim_window_rounds": 0}})
        assert zero not in joined
        assert "response from every rival" not in joined
        assert "final rival" not in joined

    def test_zero_window_rules_reach_every_provider_string(self):
        rules = load_rules_strict(RULES_PATH)
        rules["succession"]["claim_window_rounds"] = 0
        texts = self._provider_texts(rules)
        joined = " ".join(texts)
        assert claim_rule_text(rules) in joined
        assert "crowns the claimant" in joined
        assert "full round(s) uncancelled" not in joined
        assert "final rival" not in joined
