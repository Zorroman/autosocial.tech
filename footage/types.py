import hashlib
from dataclasses import dataclass


@dataclass
class VideoResult:
    provider: str
    video_id: str
    duration: int
    width: int
    height: int
    page_url: str
    download_url: str
    tags: list[str]
    orientation: str
    title: str = ""
    description: str = ""
    author: str = ""
    fps: float | None = None
    source_query: str = ""
    shot_size: str = ""
    motion_hint: str = ""

    def unique_key(self) -> str:
        provider = str(self.provider or "").strip().lower()
        video_id = str(self.video_id or "").strip()
        if provider and video_id:
            return f"{provider}:{video_id}"
        parts = [
            str(self.download_url or "").strip().lower(),
            str(self.page_url or "").strip().lower(),
            str(int(self.duration or 0)),
            str(int(self.width or 0)),
            str(int(self.height or 0)),
        ]
        normalized = "|".join(parts).strip("|")
        if normalized:
            return hashlib.sha1(normalized.encode("utf-8")).hexdigest()
        fallback = "|".join(
            [
                str(self.title or "").strip().lower(),
                " ".join(str(x or "").strip().lower() for x in (self.tags or []) if str(x or "").strip()),
                str(self.source_query or "").strip().lower(),
            ]
        )
        return hashlib.sha1(fallback.encode("utf-8")).hexdigest()
