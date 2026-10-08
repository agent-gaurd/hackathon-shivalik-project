"""Authentication and Token Management for AgentGuard Suite Gateway."""
import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path
from typing import Dict, Any, Optional

# Secret key resolution
_DEFAULT_DEV_SECRET = "agentguard-suite-dev-secret-key-2026-fallback"
SECRET_KEY = os.getenv("AG_SUITE_SECRET", _DEFAULT_DEV_SECRET)
if SECRET_KEY == _DEFAULT_DEV_SECRET:
    print("\n[WARNING] AG_SUITE_SECRET not set in environment! Using development fallback secret.\n")

TOKEN_EXPIRY_SECONDS = 8 * 3600  # 8 hours
USERS_FILE = Path(__file__).parent / "users.json"


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64decode(s: str) -> bytes:
    padding = 4 - (len(s) % 4)
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


def hash_password(password: str, salt: Optional[str] = None) -> str:
    """Hash password using PBKDF2-HMAC-SHA256."""
    if not salt:
        salt = secrets.token_hex(16)
    iterations = 100_000
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations)
    return f"pbkdf2_sha256${iterations}${salt}${derived.hex()}"


def verify_password(plain_password: str, stored_hash: str) -> bool:
    """Verify plain password against stored PBKDF2 hash."""
    try:
        parts = stored_hash.split("$")
        if len(parts) != 4:
            return False
        algo, iter_str, salt, expected_hex = parts
        if algo != "pbkdf2_sha256":
            return False
        iterations = int(iter_str)
        derived = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt.encode("utf-8"), iterations)
        return hmac.compare_digest(derived.hex(), expected_hex)
    except Exception:
        return False


def load_users() -> Dict[str, Any]:
    """Load users from users.json, creating initial demo users if missing."""
    if not USERS_FILE.exists():
        init_users = {
            "admin": {
                "username": "admin",
                "name": "Administrator",
                "password_hash": hash_password("admin123"),
                "allowed_projects": ["project1", "project2"]
            },
            "analyst1": {
                "username": "analyst1",
                "name": "UPI Fraud Analyst",
                "password_hash": hash_password("analyst123"),
                "allowed_projects": ["project1"]
            },
            "analyst2": {
                "username": "analyst2",
                "name": "Money Map Analyst",
                "password_hash": hash_password("analyst234"),
                "allowed_projects": ["project2"]
            }
        }
        USERS_FILE.write_text(json.dumps(init_users, indent=2), encoding="utf-8")
        return init_users
    try:
        return json.loads(USERS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def create_token(user: Dict[str, Any], project: Optional[str] = None) -> str:
    """Generate signed HMAC-SHA256 JWT-compatible token."""
    header = {"alg": "HS256", "typ": "JWT"}
    now_ts = int(time.time())
    payload = {
        "sub": user["username"],
        "name": user.get("name", user["username"]),
        "allowed_projects": user.get("allowed_projects", []),
        "project": project,
        "iat": now_ts,
        "exp": now_ts + TOKEN_EXPIRY_SECONDS
    }
    header_str = _b64encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_str = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_str}.{payload_str}".encode("utf-8")
    sig = hmac.new(SECRET_KEY.encode("utf-8"), signing_input, hashlib.sha256).digest()
    sig_str = _b64encode(sig)
    return f"{header_str}.{payload_str}.{sig_str}"


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and verify HMAC-SHA256 signature and expiration."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header_str, payload_str, sig_str = parts
        signing_input = f"{header_str}.{payload_str}".encode("utf-8")
        expected_sig = hmac.new(SECRET_KEY.encode("utf-8"), signing_input, hashlib.sha256).digest()
        actual_sig = _b64decode(sig_str)
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None
        payload = json.loads(_b64decode(payload_str).decode("utf-8"))
        if "exp" in payload and payload["exp"] < int(time.time()):
            return None
        return payload
    except Exception:
        return None
