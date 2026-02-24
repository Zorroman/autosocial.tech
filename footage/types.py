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
