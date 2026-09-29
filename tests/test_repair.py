# Flip bytes and confirm repair works, then fails past the limit
"""
tests/test_repair.py

Unit tests for stowaway/repair.py using pytest.
"""

import pytest
from stowaway.repair import protect, repair


class TestReedSolomonRepair:
    def test_protect_and_repair_happy_path(self):
        """Verify basic encoding and decoding without corruption."""
        payload = b"Interstellar Steganography Payload"
        protected = protect(payload, nsym=32)
        repaired = repair(protected, nsym=32)
        assert repaired == payload

    def test_repair_corrupted_bytes_within_capacity(self):
        """Verify recovery when byte corruptions are within ECC capacity (<= nsym // 2)."""
        payload = b"Radiation Proof Data Stream"
        nsym = 32
        protected = bytearray(protect(payload, nsym=nsym))

        # Corrupt 12 bytes (max capacity for nsym=32 is 16 bytes)
        for i in range(12):
            protected[i] ^= 0xFF

        repaired = repair(bytes(protected), nsym=nsym)
        assert repaired == payload

    def test_repair_exceeds_capacity_raises_value_error(self):
        """Verify that corruption exceeding ECC capacity raises ValueError."""
        payload = b"Unrecoverable Payload"
        nsym = 32
        protected = bytearray(protect(payload, nsym=nsym))

        # Corrupt 20 bytes (exceeds max capacity of 16 bytes)
        for i in range(20):
            protected[i] ^= 0xFF

        with pytest.raises(ValueError, match="Corruption exceeds error correction capacity."):
            repair(bytes(protected), nsym=nsym)

    def test_invalid_inputs(self):
        """Verify input type and value validation guards."""
        with pytest.raises(TypeError):
            protect("string_data", nsym=32)  # type: ignore
        with pytest.raises(TypeError):
            repair("string_data", nsym=32)  # type: ignore
        with pytest.raises(ValueError):
            protect(b"", nsym=32)
        with pytest.raises(ValueError):
            repair(b"", nsym=32)
        with pytest.raises(ValueError):
            protect(b"valid", nsym=0)
        with pytest.raises(ValueError):
            repair(b"valid", nsym=0)