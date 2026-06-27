"""Application-layer PII encryption (Part 10).

Two independent primitives, two independent keys:

1. **Envelope encryption** (confidentiality) — AES-256-GCM. The data-encryption
   key (DEK) is produced by a KMS CMK via GenerateDataKey; the KMS-wrapped DEK is
   stored INLINE with each ciphertext, so decrypt is self-contained (kms:Decrypt
   the wrapped DEK, then AES-GCM open). Randomized nonce ⇒ ciphertext is NOT
   searchable — that's intentional.

2. **Blind index** (searchable equality) — HMAC-SHA256 over the *normalized*
   plaintext, keyed by a SEPARATE secret (Secrets Manager). Deterministic ⇒
   supports exact-match lookup + dedup uniques WITHOUT storing plaintext. The two
   keys are kept apart so leaking one grants neither the other's capability.

Key mode:
- `settings.pii_kms_key_id` set  → KMS mode (deployed).
- empty                          → LOCAL mode (fixed dev key) so the local loop /
  tests run without AWS. LOCAL keys are clearly not-for-prod.

Ciphertext layout (bytes): VERSION(1) | len(wrapped_dek) u16-be | wrapped_dek | nonce(12) | ct+tag
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import struct
import threading

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy.types import LargeBinary, TypeDecorator

from .config import settings

VERSION = 1
_NONCE = 12

# Fixed, well-known LOCAL keys (only used when no KMS key is configured). Their
# whole point is reproducibility for the local loop + tests — never used in prod.
_LOCAL_DEK = hashlib.sha256(b"sps-local-pii-dek-not-for-prod").digest()
_LOCAL_INDEX_KEY = hashlib.sha256(b"sps-local-pii-index-key-not-for-prod").digest()


def _maybe_b64(value: str) -> bytes:
    try:
        return base64.b64decode(value, validate=True)
    except Exception:  # noqa: BLE001 — fall back to raw bytes
        return value.encode("utf-8")


class _KeyManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._enc: tuple[bytes, bytes] | None = None   # (plaintext_dek, wrapped_dek)
        self._dec: dict[bytes, bytes] = {}             # wrapped_dek -> plaintext_dek
        self._kms = None

    @property
    def kms_mode(self) -> bool:
        return bool(settings.pii_kms_key_id)

    def _kms_client(self):
        if self._kms is None:
            import boto3  # lazy: avoid AWS import/credentials in local mode
            self._kms = boto3.client("kms", region_name=settings.aws_region)
        return self._kms

    def _local_dek(self) -> bytes:
        return _maybe_b64(settings.pii_local_dek) if settings.pii_local_dek else _LOCAL_DEK

    def encryption_key(self) -> tuple[bytes, bytes]:
        """Return (plaintext_dek, wrapped_dek), generating + caching once."""
        with self._lock:
            if self._enc is None:
                if self.kms_mode:
                    resp = self._kms_client().generate_data_key(
                        KeyId=settings.pii_kms_key_id, KeySpec="AES_256"
                    )
                    self._enc = (resp["Plaintext"], resp["CiphertextBlob"])
                else:
                    self._enc = (self._local_dek(), b"")
            return self._enc

    def decryption_key(self, wrapped: bytes) -> bytes:
        if not wrapped:                       # local-mode ciphertext
            return self._local_dek()
        with self._lock:
            if wrapped not in self._dec:
                resp = self._kms_client().decrypt(
                    CiphertextBlob=wrapped, KeyId=settings.pii_kms_key_id
                )
                self._dec[wrapped] = resp["Plaintext"]
            return self._dec[wrapped]

    def index_key(self) -> bytes:
        return _maybe_b64(settings.pii_index_key) if settings.pii_index_key else _LOCAL_INDEX_KEY


_km = _KeyManager()


def encrypt(plaintext: str | None) -> bytes | None:
    if plaintext is None:
        return None
    dek, wrapped = _km.encryption_key()
    nonce = os.urandom(_NONCE)
    ct = AESGCM(dek).encrypt(nonce, plaintext.encode("utf-8"), None)
    return bytes([VERSION]) + struct.pack(">H", len(wrapped)) + wrapped + nonce + ct


def decrypt(blob: bytes | None) -> str | None:
    if blob is None:
        return None
    blob = bytes(blob)
    if not blob or blob[0] != VERSION:
        raise ValueError("unrecognized PII ciphertext")
    wlen = struct.unpack(">H", blob[1:3])[0]
    off = 3
    wrapped = blob[off:off + wlen]; off += wlen
    nonce = blob[off:off + _NONCE]; off += _NONCE
    ct = blob[off:]
    dek = _km.decryption_key(wrapped)
    return AESGCM(dek).decrypt(nonce, ct, None).decode("utf-8")


def blind_index(value: str | None) -> bytes | None:
    """Deterministic HMAC for exact-match lookup/dedup. Caller passes the already
    normalized value (e.g. normalize_phone / validate_pan output)."""
    if value is None:
        return None
    return hmac.new(_km.index_key(), value.encode("utf-8"), hashlib.sha256).digest()


class EncryptedStr(TypeDecorator):
    """Transparent column encryption: encrypt-on-write, decrypt-on-read. Stored as
    bytea. Because it operates at the persistence boundary, EVERY write path
    (including the existing POST /api/candidates) is covered automatically."""

    impl = LargeBinary
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return encrypt(value)

    def process_result_value(self, value, dialect):
        return decrypt(value) if value is not None else None
