"""NOAA proton flux and simulated storm damage for Stowaway."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import requests
from PIL import Image


NOAA_URL = (
    "https://services.swpc.noaa.gov/json/goes/primary/"
    "integral-protons-1-day.json"
)

DEFAULT_CACHE_PATH = Path("data/noaa_cache.json")
REQUEST_TIMEOUT_SECONDS = 8

FLUX_LOW_PFU = 0.1
FLUX_HIGH_PFU = 1000.0

# Probability that an individual BIT is flipped.
#
# These are simulation parameters, NOT a physical radiation model.
PROBABILITY_LOW = 0.000001
PROBABILITY_HIGH = 0.10


@dataclass
class FluxReading:
    """A proton-flux reading and whether it came from NOAA or cache."""

    flux_pfu: float
    observed_at: str | None
    from_cache: bool


def fetch_proton_flux(
    cache_path: str | Path = DEFAULT_CACHE_PATH,
) -> FluxReading:

    cache_path = Path(cache_path)

    try:
        response = requests.get(
            NOAA_URL,
            timeout=REQUEST_TIMEOUT_SECONDS
        )

        response.raise_for_status()
        rows = response.json()

        flux, observed_at = _find_latest_flux(rows)

        if flux is None:
            raise ValueError(
                "NOAA response contained no usable proton flux"
            )

        reading = FluxReading(
            flux_pfu=flux,
            observed_at=observed_at,
            from_cache=False,
        )

        _save_cache(cache_path, reading)

        return reading

    except (
        requests.RequestException,
        ValueError,
        TypeError
    ) as error:

        cached = _load_cache(cache_path)

        if cached is not None:
            return cached

        raise RuntimeError(
            "NOAA data could not be fetched, and no valid cache is available."
        ) from error


def flux_to_probability(flux_pfu: float) -> float:
    """
    Convert proton flux to simulated probability of flipping
    an individual image bit.

    This is a project-defined simulation, not a physical
    radiation damage model.
    """

    flux_pfu = float(flux_pfu)

    if not math.isfinite(flux_pfu) or flux_pfu < 0:
        raise ValueError(
            "flux_pfu must be a finite, non-negative number"
        )

    bounded_flux = min(
        max(flux_pfu, FLUX_LOW_PFU),
        FLUX_HIGH_PFU
    )

    fraction = (
        math.log10(bounded_flux) -
        math.log10(FLUX_LOW_PFU)
    ) / (
        math.log10(FLUX_HIGH_PFU) -
        math.log10(FLUX_LOW_PFU)
    )

    return PROBABILITY_LOW + fraction * (
        PROBABILITY_HIGH - PROBABILITY_LOW
    )


def damage_image(
    image: Image.Image,
    probability: float,
    rng_seed: int | None = None,
) -> tuple[Image.Image, int]:

    """
    Randomly flip individual bits throughout the RGB image.

    probability = probability that each individual bit flips.

    Example:
        probability = 0.01
        approximately 1% of all image bits are flipped.

    Returns:
        damaged image
        number of flipped bits
    """

    probability = float(probability)

    if not math.isfinite(probability) or not 0 <= probability <= 1:
        raise ValueError(
            "probability must be between 0 and 1"
        )

    pixel_values = np.array(
        image.convert("RGB"),
        dtype=np.uint8,
        copy=True,
    )

    rng = np.random.default_rng(rng_seed)

    # One random number for every BIT.
    random_values = rng.random(
        (*pixel_values.shape, 8)
    )

    # Decide which individual bits are damaged.
    should_flip = random_values < probability

    # Flip each selected bit.
    for bit in range(8):

        mask = (
            should_flip[..., bit]
            .astype(np.uint8)
            << bit
        )

        pixel_values ^= mask

    flip_count = int(np.count_nonzero(should_flip))

    damaged_image = Image.fromarray(
        pixel_values,
        mode="RGB"
    )

    return damaged_image, flip_count


def _find_latest_flux(
    rows: Any,
) -> tuple[float | None, str | None]:

    if not isinstance(rows, list):
        return None, None

    for row in reversed(rows):

        if not isinstance(row, dict):
            continue

        observed_at = row.get("time_tag")
        value = _extract_flux_value(row)

        if (
            value is not None
            and math.isfinite(value)
            and value >= 0
        ):
            return value, observed_at

    return None, None


def _extract_flux_value(
    row: dict[str, Any]
) -> float | None:

    preferred_columns = (
        ">10 MeV",
        ">=10 MeV",
        "10 MeV",
        "flux",
    )

    for column in preferred_columns:

        if column in row:

            try:
                return float(row[column])

            except (
                TypeError,
                ValueError
            ):
                pass

    if "flux" in row:

        energy = str(
            row.get("energy", "")
        )

        if (
            not energy
            or "10" in energy
            or ">" not in energy
        ):

            try:
                return float(row["flux"])

            except (
                TypeError,
                ValueError
            ):
                return None

    for column, value in row.items():

        if "MeV" in str(column):

            try:
                return float(value)

            except (
                TypeError,
                ValueError
            ):
                continue

    return None


def _save_cache(
    cache_path: Path,
    reading: FluxReading
) -> None:

    cache_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    cache_data = {
        "flux_pfu": reading.flux_pfu,
        "observed_at": reading.observed_at,
        "cached_at": datetime.now(
            timezone.utc
        ).isoformat(),
    }

    temporary_path = cache_path.with_suffix(
        cache_path.suffix + ".tmp"
    )

    temporary_path.write_text(
        json.dumps(
            cache_data,
            indent=2
        ),
        encoding="utf-8",
    )

    temporary_path.replace(cache_path)


def _load_cache(
    cache_path: Path
) -> FluxReading | None:

    try:

        cache_data = json.loads(
            cache_path.read_text(
                encoding="utf-8"
            )
        )

        flux_pfu = float(
            cache_data["flux_pfu"]
        )

        if (
            not math.isfinite(flux_pfu)
            or flux_pfu < 0
        ):
            return None

        return FluxReading(
            flux_pfu=flux_pfu,
            observed_at=cache_data.get(
                "observed_at"
            ),
            from_cache=True,
        )

    except (
        OSError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        ValueError,
    ):
        return None


# Get proton flux from NOAA
reading = fetch_proton_flux()

# Convert proton flux into simulated damage probability
probability = flux_to_probability(reading.flux_pfu)

# Ask the user for an image
image_path = input("Enter the path of your image: ")

# Open the image
image = Image.open(image_path)

# Simulate radiation damage
damaged_image, flip_count = damage_image(
    image,
    probability,
    rng_seed=42
)

# Save the damaged image
damaged_image.save("damaged_image.png")

# Display information
print()
print("----- STOWAWAY SIMULATION -----")
print("Proton flux:", reading.flux_pfu, "pfu")
print("Observed at:", reading.observed_at)
print("From cache:", reading.from_cache)
print("Simulated probability:", probability)
print("Values affected:", flip_count)
print("Damaged image saved as: damaged_image.png")