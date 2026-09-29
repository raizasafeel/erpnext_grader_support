import base64
import binascii
import hashlib
import time
from collections.abc import Mapping
from urllib.parse import urlparse

import frappe
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from frappe import _
from frappe.utils import get_url

MAX_SKEW_SECONDS = 300
MAX_BODY_BYTES = 256 * 1024

# key id -> Ed25519 public key PEM. Rotate by adding the new key in one
# release and removing the old one in a later release.
PUBLIC_KEYS: dict[str, str] = {}


def signing_message(host: str, timestamp: str, path: str, body: bytes) -> bytes:
	return f"{host}\n{timestamp}\n{path}\n{hashlib.sha256(body).hexdigest()}".encode()


def verify(
	headers: Mapping[str, str], host: str, path: str, body: bytes, now: float | None = None
) -> bool:
	key_pem = PUBLIC_KEYS.get(headers.get("X-Grader-Key-Id") or "")
	timestamp = headers.get("X-Grader-Timestamp") or ""
	signature = headers.get("X-Grader-Signature") or ""
	if not key_pem or not timestamp.isdigit() or not signature or len(body) > MAX_BODY_BYTES:
		return False
	now = time.time() if now is None else now
	if abs(now - int(timestamp)) > MAX_SKEW_SECONDS:
		return False
	try:
		load_pem_public_key(key_pem.encode()).verify(
			base64.b64decode(signature, validate=True),
			signing_message(host, timestamp, path, body),
		)
	except (InvalidSignature, ValueError, binascii.Error):
		return False
	return True


def require_signature() -> None:
	request = frappe.request
	host = (request.host or "").rsplit(":", 1)[0].lower()
	own_host = (urlparse(get_url()).hostname or "").lower()
	if host != own_host or not verify(request.headers, host, request.path, request.get_data()):
		frappe.throw(_("Forbidden"), frappe.PermissionError)
