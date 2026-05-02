import sys
import binascii
import getpass
import hashlib
import secrets

def hash_password(password: str, iterations: int = 260_000) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256%{iterations}%{binascii.hexlify(salt).decode()}%{binascii.hexlify(dk).decode()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations, salt_hex, hash_hex = stored_hash.split("%", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = binascii.unhexlify(salt_hex)
        expected = binascii.unhexlify(hash_hex)
        derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
        return secrets.compare_digest(derived, expected)
    except Exception:
        return False


def main():
    print("\n" + "="*55)
    print("  Password Hash Generator")
    print("="*55)
    pwd = getpass.getpass("Enter the password to hash: ")
    if not pwd:
        print("Error: Password cannot be empty.")
        exit(1)
    pwd_confirm = getpass.getpass("Confirm password: ")
    if pwd != pwd_confirm:
        print("Error: Passwords do not match.")
        exit(1)
    hashed = hash_password(pwd)
    print("\nSuccessfully generated password hash:")
    print(hashed)
    print("\nUsage options:")
    print("1. Set environment variable:")
    print(f"   export REMOTE_CAMERA_PASSWORD_HASH='{hashed}'")
    print("\n2. Pass as CLI argument:")
    print(f"   python -m RemoteCameraMonitoring.server --password-hash '{hashed}'")
    print("\nKeep this hash secure. Do NOT share it publicly.")
    print("="*55 + "\n")


if __name__ == "__main__":
    sys.exit(main())
