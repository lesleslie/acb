# Secure Action

The `secure` action provides pure utility functions for cryptographic operations, secure token generation, password handling, and data protection.

## Overview

This action includes cryptographically secure functions for token generation, password management, data encryption, and message authentication. All functions are stateless and use industry-standard algorithms.

## Usage

```python
from acb.actions.secure import secure

# Token generation
api_key = secure.generate_api_key(32)  # URL-safe API key
token = secure.generate_token(16)  # Secure token
password = secure.generate_password(12, True)  # Complex password

# Password hashing and verification
password_hash, salt = secure.hash_password("mypassword")
is_valid = secure.verify_password("mypassword", password_hash, salt)  # True

# Data encryption/decryption
key = secure.generate_encryption_key("my_secret_password")
encrypted = secure.encrypt_data("sensitive data", key)
decrypted = secure.decrypt_data(encrypted, key)  # "sensitive data"

# Message authentication
signature = secure.create_hmac_signature("message", "secret_key")
is_authentic = secure.verify_hmac_signature("message", signature, "secret_key")  # True

# Password strength validation
strength = secure.validate_password_strength("MyP@ssw0rd123")
# Returns: {"length_ok": True, "has_uppercase": True, "has_lowercase": True,
#          "has_digits": True, "has_symbols": True}

# Secure comparison (timing-safe)
is_equal = secure.secure_compare("secret1", "secret2")  # False
```

## Available Methods

### Token and Key Generation

- `secure.generate_token(length)` - Generate cryptographically secure token
- `secure.generate_api_key(length)` - Generate secure API key
- `secure.generate_password(length, include_symbols)` - Generate complex password
- `secure.generate_salt(length)` - Generate cryptographic salt
- `secure.generate_encryption_key(password, salt)` - Derive encryption key from password

### Password Management

- `secure.hash_password(password, salt)` - Hash password with PBKDF2-SHA256
- `secure.verify_password(password, hash, salt)` - Verify password against hash
- `secure.validate_password_strength(password, min_length)` - Check password complexity

### Data Protection

- `secure.encrypt_data(data, key)` - Encrypt data with Fernet
- `secure.decrypt_data(encrypted_data, key)` - Decrypt data with Fernet

### Message Authentication

- `secure.create_hmac_signature(message, secret)` - Create HMAC-SHA256 signature
- `secure.verify_hmac_signature(message, signature, secret)` - Verify HMAC signature

### Secure Comparison

- `secure.secure_compare(a, b)` - Timing-safe string comparison
- `secure.constant_time_compare(a, b)` - Timing-safe bytes comparison

## Cryptographic Algorithms

### Password Hashing

- **Algorithm**: PBKDF2 with SHA-256
- **Iterations**: 100,000 (OWASP recommended minimum)
- **Salt**: 32-byte cryptographically secure random salt

### Data Encryption

- **Algorithm**: Fernet (AES 128 in CBC mode with HMAC-SHA256)
- **Key Derivation**: PBKDF2-SHA256 with 32-byte salt
- **Output**: Base64 encoded ciphertext

### Message Authentication

- **Algorithm**: HMAC-SHA256
- **Output**: Hexadecimal digest

### Token Generation

- **Source**: `secrets` module (cryptographically secure)
- **Encoding**: URL-safe Base64
- **Character Set**: Letters, digits, `-`, `_`

## Security Features

### Password Complexity

Generated passwords automatically include:

- Uppercase letters (A-Z)
- Lowercase letters (a-z)
- Digits (0-9)
- Special characters (optional): `!@#$%^&*()_+-=`

### Timing Attack Protection

- All string comparisons use `hmac.compare_digest()`
- Constant-time operations prevent timing-based attacks
- Secure comparison functions available for custom use

### Secure Random Generation

- Uses `secrets` module for cryptographically strong randomness
- Suitable for passwords, tokens, and cryptographic keys
- Platform-specific secure random number generators

## Examples

### API Key Management

```python
from acb.actions.secure import secure


class APIKeyManager:
    def __init__(self):
        self.keys = {}

    def create_key(self, user_id: str) -> str:
        """Create new API key for user."""
        api_key = secure.generate_api_key(32)
        # Hash the key for storage (only store hash, not plaintext)
        key_hash, salt = secure.hash_password(api_key)
        self.keys[user_id] = {"hash": key_hash, "salt": salt}
        return api_key  # Return to user (only time they see it)

    def verify_key(self, user_id: str, provided_key: str) -> bool:
        """Verify API key."""
        if user_id not in self.keys:
            return False
        stored = self.keys[user_id]
        return secure.verify_password(provided_key, stored["hash"], stored["salt"])
```

### Data Protection

```python
from acb.actions.secure import secure


def protect_sensitive_data(data: str, user_password: str) -> str:
    """Encrypt sensitive data with user password."""
    # Generate encryption key from password
    salt = secure.generate_salt(32)
    key = secure.generate_encryption_key(user_password, salt.encode())

    # Encrypt the data
    encrypted = secure.encrypt_data(data, key)

    # Return salt + encrypted data (salt needed for decryption)
    return f"{salt}:{encrypted}"


def recover_sensitive_data(protected_data: str, user_password: str) -> str:
    """Decrypt sensitive data with user password."""
    salt_hex, encrypted = protected_data.split(":", 1)
    salt = bytes.fromhex(salt_hex)

    # Regenerate key from password and salt
    key = secure.generate_encryption_key(user_password, salt)

    # Decrypt the data
    return secure.decrypt_data(encrypted, key)
```

### Message Integrity

```python
from acb.actions.secure import secure


def sign_message(message: str, secret_key: str) -> dict:
    """Sign message for integrity verification."""
    signature = secure.create_hmac_signature(message, secret_key)
    return {"message": message, "signature": signature, "timestamp": time.time()}


def verify_message(signed_data: dict, secret_key: str) -> bool:
    """Verify message integrity."""
    return secure.verify_hmac_signature(
        signed_data["message"], signed_data["signature"], secret_key
    )
```

## Error Handling

The secure action raises `SecurityError` exceptions for cryptographic failures:

```python
from acb.actions.secure import secure, SecurityError

try:
    key = b"invalid_key"  # Wrong key size
    encrypted = secure.encrypt_data("data", key)
except SecurityError as e:
    print(f"Encryption failed: {e}")
```

## Best Practices

1. **Key Management**: Never store encryption keys with encrypted data
1. **Password Storage**: Always hash passwords, never store plaintext
1. **Token Handling**: Generate tokens server-side, validate on each request
1. **Salt Usage**: Use unique salts for each password hash
1. **Secure Comparison**: Always use timing-safe comparison for secrets
1. **Key Derivation**: Use strong passwords for key derivation
1. **Random Generation**: Use the `secure` action for all random values

## Performance Considerations

- PBKDF2 with 100,000 iterations provides security but adds ~100ms latency
- Fernet encryption/decryption is fast for typical data sizes
- HMAC operations are very fast and suitable for high-frequency use
- Token generation is fast and suitable for real-time use

## Related Actions

- [validate](../validate/README.md) - Input validation and security checks
- [hash](../hash/README.md) - Fast hashing and checksum functions
- [encode](../encode/README.md) - Data serialization and encoding
