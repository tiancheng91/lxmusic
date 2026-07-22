"""数据模型。"""

from dataclasses import dataclass, field


@dataclass
class MusicItem:
    id: int
    songmid: str
    title: str
    artist: str
    album: str | None = None
    albummid: str | None = None
    artwork: str | None = None
    qualities: dict[str, dict] = field(default_factory=dict)
    source: str = "tx"


@dataclass
class AlbumItem:
    id: int
    album_mid: str
    title: str
    artist: str | None = None
    artwork: str | None = None
    date: str | None = None
    singer_mid: str | None = None
    source: str = "tx"
