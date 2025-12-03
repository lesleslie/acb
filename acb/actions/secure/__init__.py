"""Cryptographic and security utilities for ACB framework.

This action provides pure utility functions for cryptographic operations,
secure token generation, password handling, and data protection.
"""

import base64
import hashlib
import hmac
import secrets
import string

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Import security pattern detection functions
from .security_patterns import detect_path_traversal, detect_sql_injection, detect_xss

__all__: list[str] = [
    "detect_path_traversal",
    "detect_sql_injection",
    "detect_xss",
    "secure",
]


class SecurityError(Exception):
    """Raised when security operations fail."""


class Secure:
    """Pure utility functions for cryptographic and security operations."""

    @staticmethod
    def generate_token(length: int = 32) -> str:
        """Generate a cryptographically secure URL-safe token.

        Args:
            length: Token length (default: 32)

        Returns:
            URL-safe base64 encoded token
        """
        return secrets.token_urlsafe(length)

    @staticmethod
    def generate_api_key(length: int = 32) -> str:
        """Generate a secure API key.

        Args:
            length: API key length (default: 32)

        Returns:
            URL-safe base64 encoded API key
        """
        return secrets.token_urlsafe(length)

    @staticmethod
    def generate_password(length: int = 16, include_symbols: bool = True) -> str:
        """Generate a secure password with complexity requirements.

        Args:
            length: Password length (default: 16)
            include_symbols: Include special characters (default: True)

        Returns:
            Secure password meeting complexity requirements
        """
        chars = string.ascii_letters + string.digits
        if include_symbols:
            chars += "!@#$%^&*()_+-="

        password = "".join(secrets.choice(chars) for _ in range(length))

        # Ensure password meets complexity requirements
        if not any(c.isupper() for c in password):
            password = password[:-1] + secrets.choice(string.ascii_uppercase)
        if not any(c.islower() for c in password):
            password = password[:-1] + secrets.choice(string.ascii_lowercase)
        if not any(c.isdigit() for c in password):
            password = password[:-1] + secrets.choice(string.digits)
        if include_symbols and not any(c in "!@#$%^&*()_+-=" for c in password):
            password = password[:-1] + secrets.choice("!@#$%^&*()_+-=")

        return password

    @staticmethod
    def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
        """Hash password with salt using PBKDF2-SHA256.

        Args:
            password: Password to hash
            salt: Salt to use (generated if None)

        Returns:
            Tuple of (password_hash, salt)
        """
        if salt is None:
            salt = secrets.token_hex(32)

        password_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode(),
            salt.encode(),
            100000,
        )
        return password_hash.hex(), salt

    @staticmethod
    def verify_password(password: str, password_hash: str, salt: str) -> bool:
        """Verify password against hash.

        Args:
            password: Password to verify
            password_hash: Stored password hash
            salt: Salt used for hashing

        Returns:
            True if password matches, False otherwise
        """
        computed_hash, _ = Secure.hash_password(password, salt)
        return Secure.secure_compare(computed_hash, password_hash)

    @staticmethod
    def secure_compare(a: str, b: str) -> bool:
        """Perform timing-safe string comparison.

        Args:
            a: First string
            b: Second string

        Returns:
            True if strings are equal, False otherwise
        """
        return hmac.compare_digest(a, b)

    @staticmethod
    def create_hmac_signature(message: str, secret: str) -> str:
        """Create HMAC-SHA256 signature for message authentication.

        Args:
            message: Message to sign
            secret: Secret key for signing

        Returns:
            Hexadecimal HMAC signature
        """
        return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()

    @staticmethod
    def verify_hmac_signature(message: str, signature: str, secret: str) -> bool:
        """Verify HMAC-SHA256 signature for message authentication.

        Args:
            message: Original message
            signature: HMAC signature to verify
            secret: Secret key used for signing

        Returns:
            True if signature is valid, False otherwise
        """
        expected_signature = Secure.create_hmac_signature(message, secret)
        return Secure.secure_compare(signature, expected_signature)

    @staticmethod
    def generate_encryption_key(password: str, salt: bytes | None = None) -> bytes:
        """Generate encryption key from password using PBKDF2.

        Args:
            password: Password to derive key from
            salt: Salt for key derivation (generated if None)

        Returns:
            32-byte encryption key
        """
        if salt is None:
            salt = secrets.token_bytes(32)

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        return kdf.derive(password.encode())

    @staticmethod
    def encrypt_data(data: str, key: bytes) -> str:
        """Encrypt data using Fernet symmetric encryption.

        Args:
            data: Data to encrypt
            key: 32-byte encryption key

        Returns:
            Base64 encoded encrypted data
        """
        try:
            fernet = Fernet(base64.urlsafe_b64encode(key))
            encrypted = fernet.encrypt(data.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        except Exception as e:
            msg = f"Encryption failed: {e}"
            raise SecurityError(msg) from e

    @staticmethod
    def decrypt_data(encrypted_data: str, key: bytes) -> str:
        """Decrypt data using Fernet symmetric encryption.

        Args:
            encrypted_data: Base64 encoded encrypted data
            key: 32-byte encryption key

        Returns:
            Decrypted plaintext data
        """
        try:
            fernet = Fernet(base64.urlsafe_b64encode(key))
            encrypted = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted = fernet.decrypt(encrypted)
            return decrypted.decode()
        except Exception as e:
            msg = f"Decryption failed: {e}"
            raise SecurityError(msg) from e

    @staticmethod
    def validate_password_strength(
        password: str,
        min_length: int = 8,
    ) -> dict[str, bool]:
        """Validate password strength against common requirements.

        Args:
            password: Password to validate
            min_length: Minimum required length

        Returns:
            Dictionary with validation results
        """
        return {
            "length_ok": len(password) >= min_length,
            "has_uppercase": any(c.isupper() for c in password),
            "has_lowercase": any(c.islower() for c in password),
            "has_digits": any(c.isdigit() for c in password),
            "has_symbols": any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password),
        }

    @staticmethod
    def generate_salt(length: int = 32) -> str:
        """Generate a cryptographically secure salt.

        Args:
            length: Salt length in bytes (default: 32)

        Returns:
            Hexadecimal encoded salt
        """
        return secrets.token_hex(length)

    @staticmethod
    def constant_time_compare(a: bytes, b: bytes) -> bool:
        """Perform constant-time comparison of byte sequences.

        Args:
            a: First byte sequence
            b: Second byte sequence

        Returns:
            True if sequences are equal, False otherwise
        """
        return hmac.compare_digest(a, b)


# Export an instance
secure = Secure()
