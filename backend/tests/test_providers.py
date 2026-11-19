from datetime import date
from decimal import Decimal

import httpx
import pytest
from pydantic import SecretStr

from app.config import Settings
from app.providers import FredAPIProvider, FredCSVProvider, ProviderError, parse_observations, parse_value


def settings(**kwargs):
    return Settings(_env_file=None, fred_api_key=SecretStr("test-key"), **kwargs)


def test_parse_fred_json_and_missing():
    rows = parse_observations({"observations": [
        {"date": "2024-01-01", "value": "308.417", "realtime_start": "2024-02-13", "realtime_end": "2024-02-13"},
        {"date": "2024-02-01", "value": ".", "realtime_start": "2024-03-12", "realtime_end": "9999-12-31"},
    ]})
    assert rows[0].value == Decimal("308.417")
    assert rows[0].realtime_start == date(2024, 2, 13)
    assert rows[1].value is None and rows[1].raw_value == "."


@pytest.mark.parametrize("raw", [".", "", "NA", "NaN"])
def test_missing(raw):
    assert parse_value(raw) is None


@pytest.mark.parametrize("raw", ["garbage", "Infinity", "-Infinity"])
def test_invalid_value(raw):
    with pytest.raises(ProviderError):
        parse_value(raw)


def test_retry_429_timeout_then_success(caplog):
    calls, sleeps = [], []
    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(429, headers={"Retry-After": "5"})
        if len(calls) == 2:
            raise httpx.ReadTimeout("secret must never be logged", request=request)
        return httpx.Response(200, json={"observations": [], "count": 0})
    provider = FredAPIProvider(settings(), client=httpx.Client(transport=httpx.MockTransport(handler)), sleep=sleeps.append)
    assert provider.observations("DFF", date(2024, 1, 1), date(2024, 2, 1)) == []
    assert len(calls) == 3 and any(s >= 5 for s in sleeps)
    assert "test-key" not in caplog.text and "secret must" not in caplog.text


def test_non_retryable_and_redacted():
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(400, json={"error_message": "test-key"})
    provider = FredAPIProvider(settings(), client=httpx.Client(transport=httpx.MockTransport(handler)), sleep=lambda _: None)
    with pytest.raises(ProviderError, match="HTTP 400") as error:
        provider.metadata("DFF")
    assert len(calls) == 1 and "test-key" not in str(error.value)


def test_retry_exhaustion():
    provider = FredAPIProvider(settings(fred_max_retries=1),
        client=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(503))), sleep=lambda _: None)
    with pytest.raises(ProviderError, match="exhausted retries"):
        provider.metadata("DFF")


def test_csv_parser_and_provenance():
    provider = FredCSVProvider(settings(), client=httpx.Client(transport=httpx.MockTransport(
        lambda r: httpx.Response(200, text="observation_date,DFF\n2024-01-01,5.33\n2024-01-02,.\n"))), sleep=lambda _: None)
    rows = provider.observations("DFF", date(2024, 1, 1), date(2024, 1, 2))
    assert rows[0].value == Decimal("5.33")
    assert rows[1].value is None and rows[0].realtime_start is None


def test_api_pagination():
    def handler(request):
        n = int(request.url.params["offset"])
        return httpx.Response(200, json={"count": 2, "observations": [dict(date=f"2024-01-0{n+1}", value="1", realtime_start="2024-02-01", realtime_end="2024-02-01")]})
    provider = FredAPIProvider(settings(), client=httpx.Client(transport=httpx.MockTransport(handler)), sleep=lambda _: None)
    assert len(provider.observations("DFF", date(2024, 1, 1), date(2024, 2, 1))) == 2


def test_key_required():
    with pytest.raises(ProviderError, match="required"):
        FredAPIProvider(Settings(_env_file=None, fred_api_key=SecretStr("")))


@pytest.mark.parametrize("payload", [{}, {"observations": [{"value": "1"}]}])
def test_bad_shape(payload):
    with pytest.raises(ProviderError):
        parse_observations(payload)


def test_source_default_date_pins_pagination_across_local_midnight():
    calls=[]
    def handler(request):
        calls.append(dict(request.url.params))
        n=int(request.url.params['offset'])
        return httpx.Response(200,json={'realtime_start':'2026-11-16','count':2,'observations':[dict(date=f'2026-11-{12+n}',value='3.88',realtime_start='2026-11-16',realtime_end='2026-11-16')]})
    provider=FredAPIProvider(settings(),client=httpx.Client(transport=httpx.MockTransport(handler)),sleep=lambda _:None)
    assert len(provider.observations('DFF',date(2026,11,1),date(2026,11,17)))==2
    assert 'realtime_start' not in calls[0]
    assert calls[1]['realtime_start']==calls[1]['realtime_end']=='2026-11-16'
