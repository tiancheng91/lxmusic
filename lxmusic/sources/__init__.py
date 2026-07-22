"""音乐源接口抽象。"""

from abc import ABC, abstractmethod

from lxmusic.models import AlbumItem, MusicItem


class Source(ABC):
    """音乐源抽象接口。"""

    @abstractmethod
    def search_music(self, query: str, page: int = 1) -> dict: ...

    @abstractmethod
    def search_album(self, query: str, page: int = 1) -> dict: ...

    @abstractmethod
    def get_music_info(self, songmid: str | None = None, song_id: int | None = None) -> MusicItem | None: ...

    @abstractmethod
    def get_album_info(self, album_mid: str) -> dict: ...

    @abstractmethod
    def get_lyric(self, songmid: str) -> dict: ...

    @abstractmethod
    def get_audio_headers(self) -> dict[str, str]:
        """播放 CDN 需要的 HTTP 请求头。"""
        return {}

    @abstractmethod
    def close(self) -> None: ...