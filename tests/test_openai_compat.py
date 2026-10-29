import httpx
import pytest

from app.llm import MockLLM, OpenAICompatLLM, get_llm


def _env(monkeypatch, **extra):
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setenv("LLM_MODEL", "some-model")
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    for k, v in extra.items():
        monkeypatch.setenv(k, v)


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


OK = {"choices": [{"message": {"content": '{"a": 1}'}}], "usage": {"prompt_tokens": 11, "completion_tokens": 5}}


def test_request_shape_and_parsing(monkeypatch):
    _env(monkeypatch)
    seen = {}

    def handler(req):
        seen["url"], seen["auth"] = str(req.url), req.headers["authorization"]
        seen["body"] = __import__("json").loads(req.content)
        return httpx.Response(200, json=OK)

    r = OpenAICompatLLM("gemini", client=_client(handler), sleep=lambda s: None).complete("SYS", "USER")
    assert r.text == '{"a": 1}' and (r.input_tokens, r.output_tokens) == (11, 5)
    assert seen["url"].endswith("/v1beta/openai/chat/completions") and seen["auth"] == "Bearer k"
    assert seen["body"]["temperature"] == 0 and seen["body"]["model"] == "some-model"
    assert [m["role"] for m in seen["body"]["messages"]] == ["system", "user"]


def test_retries_on_rate_limit_then_succeeds(monkeypatch):
    _env(monkeypatch)
    calls, sleeps = [], []

    def handler(req):
        calls.append(1)
        return httpx.Response(429, headers={"retry-after": "3"}) if len(calls) < 3 else httpx.Response(200, json=OK)

    OpenAICompatLLM("gemini", client=_client(handler), sleep=sleeps.append).complete("s", "u")
    assert len(calls) == 3 and sleeps == [3.0, 3.0]


def test_gives_up_after_repeated_failures(monkeypatch):
    _env(monkeypatch)
    llm = OpenAICompatLLM("gemini", client=_client(lambda req: httpx.Response(503)), sleep=lambda s: None)
    with pytest.raises(httpx.HTTPStatusError):
        llm.complete("s", "u")


def test_client_error_is_not_retried(monkeypatch):
    _env(monkeypatch)
    calls = []

    def handler(req):
        calls.append(1)
        return httpx.Response(401)

    with pytest.raises(httpx.HTTPStatusError):
        OpenAICompatLLM("gemini", client=_client(handler), sleep=lambda s: None).complete("s", "u")
    assert len(calls) == 1


def test_min_interval_spaces_calls(monkeypatch):
    _env(monkeypatch, LLM_MIN_INTERVAL="4")
    sleeps = []
    llm = OpenAICompatLLM("gemini", client=_client(lambda req: httpx.Response(200, json=OK)),
                          sleep=sleeps.append, clock=lambda: 100.0)
    llm.complete("s", "u")
    llm.complete("s", "u")
    assert sleeps == [4.0]


@pytest.mark.parametrize("missing", ["GEMINI_API_KEY", "LLM_MODEL"])
def test_clear_error_when_config_missing(monkeypatch, missing):
    _env(monkeypatch)
    monkeypatch.delenv(missing)
    with pytest.raises(RuntimeError):
        OpenAICompatLLM("gemini")


def test_get_llm_routes_providers(monkeypatch):
    _env(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    assert isinstance(get_llm(), OpenAICompatLLM)
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    assert isinstance(get_llm(), MockLLM)
