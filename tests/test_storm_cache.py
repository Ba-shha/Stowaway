# Offline NOAA fetch must fall back to the cache

# Offline NOAA fetch must fall back to the cache
import json

import requests

from stowaway import storm


def test_offline_uses_cache(tmp_path, monkeypatch):
    cache = tmp_path / "cache.json"
    cache.write_text(json.dumps({"flux_pfu": 2.5, "observed_at": "2026-01-01T00:00:00Z"}))

    def offline(*args, **kwargs):
        raise requests.ConnectionError

    monkeypatch.setattr(storm.requests, "get", offline)
    reading = storm.fetch_proton_flux(cache)
    assert reading.from_cache and reading.flux_pfu == 2.5


def test_probability_is_log_scaled():
    assert abs(storm.flux_to_probability(0.1) - 1e-6) < 1e-12
    assert abs(storm.flux_to_probability(1000) - 0.1) < 1e-9
    assert abs(storm.flux_to_probability(10) - 10 ** -3.5) < 1e-9