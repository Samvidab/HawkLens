"""Pydantic models for the Matterport platform, written from the confirmed schema
(see data/matterport/schema.json and .kiro/specs/matterport-platform/).

Only the fields the thin vertical slice needs are modeled now; more are added as
later tasks ingest them. `raw` always keeps the full response for traceability.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class MpAddress(BaseModel):
    """Flattened Matterport Address (search + model share the useful fields)."""

    locality: str | None = None            # city, e.g. "Houston"
    administrative_area: str | None = None  # state/region
    postal_code: str | None = None
    country_code: str | None = None
    formatted: str | None = None            # Address.address, a single-line string

    @classmethod
    def from_api(cls, a: dict | None) -> "MpAddress":
        a = a or {}
        return cls(
            locality=a.get("locality"),
            administrative_area=a.get("administrativeArea"),
            postal_code=a.get("postalCode"),
            country_code=a.get("countryCode"),
            formatted=a.get("address"),
        )


class MpGeo(BaseModel):
    lat: float | None = None
    lon: float | None = None

    @classmethod
    def from_api(cls, g: dict | None) -> "MpGeo":
        g = g or {}
        def _f(v):
            try:
                return float(v) if v is not None else None
            except (TypeError, ValueError):
                return None
        return cls(lat=_f(g.get("lat")), lon=_f(g.get("long")))


class MpModel(BaseModel):
    """Core index record for one Matterport model. Stored at models/<id>.json."""

    id: str
    name: str | None = None
    created: str | None = None
    modified: str | None = None
    address: MpAddress = Field(default_factory=MpAddress)
    geo: MpGeo = Field(default_factory=MpGeo)
    thumbnail_url: str | None = None   # short-lived signed URL (do not serve to clients)
    thumbnail_path: str | None = None  # local saved copy under cache/media (durable)
    embed_html: str | None = None    # raw <iframe> snippet from publication.embed
    show_url: str | None = None      # https://my.matterport.com/show/?m=<id>
    published: bool = False
    pi_available: bool = False
    raw: dict = Field(default_factory=dict)

    @property
    def city(self) -> str | None:
        return self.address.locality
