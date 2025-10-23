import base64
import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


SCHEME_VERSION = "SW1"
DEFAULT_SCRYPT_N = 2 ** 14
DEFAULT_SCRYPT_R = 8
DEFAULT_SCRYPT_P = 1


class CryptoError(Exception):
    pass


@dataclass(frozen=True)
class ScryptParams:
    n: int = DEFAULT_SCRYPT_N
    r: int = DEFAULT_SCRYPT_R
    p: int = DEFAULT_SCRYPT_P


def _b64encode(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _b64decode(data_b64: str) -> bytes:
    return base64.b64decode(data_b64.encode("ascii"))


def generate_salt(length: int = 16) -> bytes:
    if length < 16:
        # Ensure adequate entropy for scrypt salt
        length = 16
    return os.urandom(length)


def derive_key(passphrase: str, salt: bytes, params: Optional[ScryptParams] = None) -> bytes:
    if not isinstance(passphrase, str) or passphrase == "":
        raise CryptoError("Passphrase must be a non-empty string")
    params = params or ScryptParams()
    kdf = Scrypt(salt=salt, length=32, n=params.n, r=params.r, p=params.p)
    return kdf.derive(passphrase.encode("utf-8"))


def build_aad(sender: str, recipient: str, timestamp_s: Optional[int] = None) -> bytes:
    ts = int(timestamp_s if timestamp_s is not None else time.time())
    aad_obj = {
        "sender": sender,
        "recipient": recipient,
        "ts": ts,
    }
    # Stable JSON encoding for AAD
    aad_json = json.dumps(aad_obj, separators=(",", ":"), sort_keys=True)
    return aad_json.encode("utf-8")


def encrypt_message(
    plaintext: str,
    passphrase: str,
    *,
    sender: str,
    recipient: str,
    scrypt_params: Optional[ScryptParams] = None,
) -> Dict[str, Any]:
    if not isinstance(plaintext, str):
        raise CryptoError("Plaintext must be a string")
    if plaintext == "":
        raise CryptoError("Plaintext cannot be empty")

    params = scrypt_params or ScryptParams()
    salt = generate_salt()
    key = derive_key(passphrase, salt, params)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 96-bit nonce for AES-GCM
    aad = build_aad(sender, recipient)

    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), aad)

    return {
        "ciphertext": _b64encode(ciphertext),
        "nonce": _b64encode(nonce),
        "salt": _b64encode(salt),
        "aad": _b64encode(aad),
        "scheme": SCHEME_VERSION,
        "scrypt_n": params.n,
        "scrypt_r": params.r,
        "scrypt_p": params.p,
    }


def decrypt_message(record: Dict[str, Any], passphrase: str) -> str:
    try:
        ciphertext = _b64decode(record["ciphertext"])  # type: ignore[index]
        nonce = _b64decode(record["nonce"])  # type: ignore[index]
        salt = _b64decode(record["salt"])  # type: ignore[index]
        aad = _b64decode(record.get("aad", ""))
        scheme = record.get("scheme", SCHEME_VERSION)
        if scheme != SCHEME_VERSION:
            raise CryptoError(f"Unsupported scheme version: {scheme}")
        params = ScryptParams(
            n=int(record.get("scrypt_n", DEFAULT_SCRYPT_N)),
            r=int(record.get("scrypt_r", DEFAULT_SCRYPT_R)),
            p=int(record.get("scrypt_p", DEFAULT_SCRYPT_P)),
        )
        key = derive_key(passphrase, salt, params)
        aesgcm = AESGCM(key)
        plaintext_bytes = aesgcm.decrypt(nonce, ciphertext, aad)
        return plaintext_bytes.decode("utf-8")
    except InvalidTag as e:
        raise CryptoError("Decryption failed. Wrong passphrase or corrupted data.") from e
    except Exception as e:  # pylint: disable=broad-except
        raise CryptoError(f"Decryption error: {e}") from e
