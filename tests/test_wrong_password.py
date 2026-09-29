# Wrong password must fail
"""
tests/test_wrong_password.py

Unit tests verifying password derivation and authentication failures for stowaway/crypto.py.
"""

import pytest
from stowaway.crypto import lock, unlock


class TestWrongPassword:
    def test_unlock_with_correct_password(self):
        """Verify successful decryption when the correct password is provided."""
        message = "Secret Telemetry Data"
        password = "correct-password-2026"
        salt, token = lock(message, password)

        decrypted = unlock(token, password, salt)
        assert decrypted == message

    def test_unlock_with_wrong_password(self):
        """Verify decryption fails when an incorrect password is provided."""
        message = "Secret Telemetry Data"
        password = "correct-password-2026"
        wrong_password = "incorrect-password-2026"

        salt, token = lock(message, password)

        with pytest.raises(ValueError, match="Tampered or wrong password"):
            unlock(token, wrong_password, salt)