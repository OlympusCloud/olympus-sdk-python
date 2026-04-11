"""File storage operations backed by Cloudflare R2.

Routes: ``/storage/*`` (proxied to the media-storage worker).
"""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from olympus_sdk.http import OlympusHttpClient


class StorageService:
    """File storage operations backed by Cloudflare R2."""

    def __init__(self, http: OlympusHttpClient) -> None:
        self._http = http

    def upload(self, data: bytes, path: str) -> str:
        """Upload binary data to a path and return the public URL.

        ``path`` is the storage key (e.g. "images/menu/burger.webp").
        """
        resp = self._http.post("/storage/upload", json={
            "path": path,
            "content": base64.b64encode(data).decode(),
        })
        return resp.get("url", "")

    def get_url(self, path: str) -> str:
        """Get the public or signed URL for a stored object."""
        resp = self._http.get("/storage/url", params={"path": path})
        return resp.get("url", "")

    def presign_upload(self, path: str, *, expires_in: int | None = None) -> str:
        """Generate a pre-signed upload URL for direct client uploads.

        ``expires_in`` is the validity duration in seconds (default: 3600).
        """
        payload: dict[str, Any] = {"path": path}
        if expires_in is not None:
            payload["expires_in"] = expires_in
        resp = self._http.post("/storage/presign", json=payload)
        return resp.get("url") or resp.get("presigned_url", "")

    def delete(self, path: str) -> None:
        """Delete a stored object."""
        self._http.delete(f"/storage/objects/{path}")
