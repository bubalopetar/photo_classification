"""Shared library used by every microservice.

Kept intentionally small: cross-cutting concerns that MUST behave identically
across services — JWT verification, base settings, health probes, logging.
Business logic never lives here.

No eager submodule imports here: services import what they use directly
(`from shared.security import ...`), and not every service installs every
submodule's dependencies (classification has no PyJWT, for example).
"""
