# Tampered data must trigger the tamper error
"""
tests/test_tamper.py

Unit tests verifying payload corruption and HMAC tampering detection for stowaway/crypto.py.
"""

import pytest
from stowaway.crypto import lock, unlock


class TestTamperDetection:
    def test_unlock_with_tampered_token(self):
        """Verify decryption fails when the Fernet ciphertext token is modified."""
        message = "Secret Telemetry Data"
        password = "space-passphrase-2026"
        salt, token = lock(message, password)

        # Corrupt the ciphertext token byte array
        token_bytes = bytearray(token)
        token_bytes[10] ^= 0xFF
        tampered_token = bytes(token_bytes)

        with pytest.raises(ValueError, match="Tampered or wrong password"):
            unlock(tampered_token, password, salt)

    def test_unlock_with_tampered_salt(self):
        """Verify decryption fails when the KDF salt is modified."""
        message = "Secret Telemetry Data"
        password = "space-passphrase-2026"
        salt, token = lock(message, password)

        # Corrupt the KDF salt byte array
        salt_bytes = bytearray(salt)
        salt_bytes[0] ^= 0xFF
        tampered_salt = bytes(salt_bytes)

        with pytest.raises(ValueError, match="Tampered or wrong password"):
            unlock(token, password, tampered_salt)