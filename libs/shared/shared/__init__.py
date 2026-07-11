"""Shared library used by every microservice.

Kept intentionally small: cross-cutting concerns that MUST behave identically
across services — JWT verification, base settings, health probes, logging.
Business logic never lives here.
"""

from shared.security import JWTAuth, Principal, decode_token, encode_token

__all__ = ["JWTAuth", "Principal", "decode_token", "encode_token"]
