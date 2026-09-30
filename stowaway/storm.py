"""NOAA proton flux, a simple flux to bit-flip mapping, and the storm damage itself."""

import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import requests
from PIL import Image

NOAA_URL = "https://services.swpc.noaa.gov/json/goes/primary/integral-protons-1-day.json"
CACHE_PATH = Path(__file__).resolve().parent.parent / "data" / "noaa_cache.json"

# Our own model, not radiation physics: flux from FLUX_LOW to FLUX_HIGH (pfu) maps to a
# bit-flip probability from P_LOW to P_HIGH, evenly spaced on a log scale.
FLUX_LOW, FLUX_HIGH = 0.1, 1000.0
P_LOW, P_HIGH = 1e-6, 1e-1


@dataclass
class FluxReading:
    flux_pfu: float
    observed_at: str | None
    from_cache: bool


def fetch_proton_flux(cache_path: Path = CACHE_PATH) -> FluxReading:
    """Latest >=10 MeV proton flux from NOAA. Falls back to the cache when offline."""
    try:
        rows = requests.get(NOAA_URL, timeout=8).json()
        tens = [r for r in rows if "10 MeV" in str(r.get("energy", ""))]
        row = (tens or rows)[-1]
        reading = FluxReading(float(row["flux"]), row.get("time_tag"), False)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps({
            "flux_pfu": reading.flux_pfu,
            "observed_at": reading.observed_at,
            "cached_at": datetime.now(timezone.utc).isoformat(),
        }, indent=2))
        return reading
    except (requests.RequestException, ValueError, KeyError, IndexError, TypeError, AttributeError):
        try:
            saved = json.loads(cache_path.read_text())
            return FluxReading(float(saved["flux_pfu"]), saved.get("observed_at"), True)
        except (OSError, ValueError, KeyError):
            raise RuntimeError("NOAA is unreachable and there is no cached reading.")


def flux_to_probability(flux_pfu: float) -> float:
    """Map proton flux to the chance that any one bit flips."""
    flux = min(max(float(flux_pfu), FLUX_LOW), FLUX_HIGH)
    fraction = math.log10(flux / FLUX_LOW) / math.log10(FLUX_HIGH / FLUX_LOW)
    return P_LOW * (P_HIGH / P_LOW) ** fraction


def damage_image(image: Image.Image, probability: float, seed: int | None = None):
    """Flip each bit of the image with the given probability. Returns (image, bits flipped)."""
    if not 0 <= probability <= 1:
        raise ValueError("probability must be between 0 and 1")
    pixels = np.array(image.convert("RGB"), dtype=np.uint8)
    rng = np.random.default_rng(seed)
    flipped = 0
    for bit in range(8):  # one bit plane at a time keeps memory small
        hit = rng.random(pixels.shape) < probability
        pixels ^= hit.astype(np.uint8) << bit
        flipped += int(hit.sum())
    return Image.fromarray(pixels), flipped