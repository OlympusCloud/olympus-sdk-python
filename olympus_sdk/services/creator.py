"""Creator platform: posts, media, profiles, analytics, and AI content tools.

Wraps the Olympus Creator service (Rust) via the Go API Gateway.
Routes: ``/creator/*``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from olympus_sdk.http import OlympusHttpClient


class CreatorService:
    """Creator platform: posts, media, profiles, analytics, and AI content generation."""

    def __init__(self, http: OlympusHttpClient) -> None:
        self._http = http

    # ------------------------------------------------------------------
    # Posts
    # ------------------------------------------------------------------

    async def list_posts(
        self,
        *,
        page: int | None = None,
        limit: int | None = None,
        status: str | None = None,
    ) -> dict:
        """List creator posts with optional filters and pagination."""
        return self._http.get(
            "/creator/posts",
            params={"page": page, "limit": limit, "status": status},
        )

    async def create_post(
        self,
        *,
        title: str,
        body: str,
        tags: list[str] | None = None,
        media_ids: list[str] | None = None,
    ) -> dict:
        """Create a new post."""
        payload: dict[str, Any] = {"title": title, "body": body}
        if tags is not None:
            payload["tags"] = tags
        if media_ids is not None:
            payload["media_ids"] = media_ids
        return self._http.post("/creator/posts", json=payload)

    async def get_post(self, post_id: str) -> dict:
        """Retrieve a single post by ID."""
        return self._http.get(f"/creator/posts/{post_id}")

    async def update_post(
        self,
        post_id: str,
        *,
        title: str | None = None,
        body: str | None = None,
        tags: list[str] | None = None,
    ) -> dict:
        """Update an existing post."""
        payload: dict[str, Any] = {}
        if title is not None:
            payload["title"] = title
        if body is not None:
            payload["body"] = body
        if tags is not None:
            payload["tags"] = tags
        return self._http.patch(f"/creator/posts/{post_id}", json=payload)

    async def delete_post(self, post_id: str) -> dict:
        """Delete a post."""
        self._http.delete(f"/creator/posts/{post_id}")
        return {}

    async def publish_post(self, post_id: str) -> dict:
        """Publish a draft post, making it publicly visible."""
        return self._http.post(f"/creator/posts/{post_id}/publish")

    # ------------------------------------------------------------------
    # Media
    # ------------------------------------------------------------------

    async def list_media(
        self,
        *,
        page: int | None = None,
        limit: int | None = None,
    ) -> dict:
        """List uploaded media assets."""
        return self._http.get(
            "/creator/media",
            params={"page": page, "limit": limit},
        )

    async def initiate_upload(
        self,
        *,
        filename: str,
        content_type: str,
        size_bytes: int,
    ) -> dict:
        """Initiate a media upload and receive a presigned URL."""
        return self._http.post(
            "/creator/media/upload",
            json={
                "filename": filename,
                "content_type": content_type,
                "size_bytes": size_bytes,
            },
        )

    async def confirm_upload(self, upload_id: str) -> dict:
        """Confirm that a media upload has completed successfully."""
        return self._http.post(f"/creator/media/upload/{upload_id}/confirm")

    # ------------------------------------------------------------------
    # Profile
    # ------------------------------------------------------------------

    async def get_profile(self) -> dict:
        """Get the current creator profile."""
        return self._http.get("/creator/profile")

    async def update_profile(
        self,
        *,
        display_name: str | None = None,
        bio: str | None = None,
        avatar_url: str | None = None,
    ) -> dict:
        """Update the creator profile."""
        payload: dict[str, Any] = {}
        if display_name is not None:
            payload["display_name"] = display_name
        if bio is not None:
            payload["bio"] = bio
        if avatar_url is not None:
            payload["avatar_url"] = avatar_url
        return self._http.patch("/creator/profile", json=payload)

    # ------------------------------------------------------------------
    # Analytics
    # ------------------------------------------------------------------

    async def get_analytics_summary(
        self,
        *,
        period: str | None = None,
    ) -> dict:
        """Get an analytics summary for the creator's content."""
        return self._http.get(
            "/creator/analytics/summary",
            params={"period": period},
        )

    # ------------------------------------------------------------------
    # AI Content
    # ------------------------------------------------------------------

    async def generate_content(
        self,
        *,
        prompt: str,
        template_id: str | None = None,
        tone: str | None = None,
    ) -> dict:
        """Generate content using AI based on a prompt."""
        payload: dict[str, Any] = {"prompt": prompt}
        if template_id is not None:
            payload["template_id"] = template_id
        if tone is not None:
            payload["tone"] = tone
        return self._http.post("/creator/ai/generate", json=payload)

    async def list_ai_templates(self) -> dict:
        """List available AI content generation templates."""
        return self._http.get("/creator/ai/templates")

    # ------------------------------------------------------------------
    # Team
    # ------------------------------------------------------------------

    async def list_team(self) -> dict:
        """List team members for the creator account."""
        return self._http.get("/creator/team")

    async def invite_team_member(
        self,
        *,
        email: str,
        role: str,
    ) -> dict:
        """Invite a new team member by email."""
        return self._http.post(
            "/creator/team/invite",
            json={"email": email, "role": role},
        )
