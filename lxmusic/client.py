"""MusicClient — 组合 Source + PlayURLProvider。"""

from lxmusic.config import Config
from lxmusic.models import MusicItem
from lxmusic.sources import Source
from lxmusic.sources.tx import TXSource
from lxmusic.sources.wy import WYSource
from lxmusic.sources.local import LocalSource
from lxmusic.playurl import PlayURLProvider, ShiqianjiangProvider

_SOURCES: dict[str, type[Source]] = {
    "tx": TXSource,
    "wy": WYSource,
    "local": LocalSource,
}


class MusicClient:
    """组合音乐源（搜索/详情）和播放链接提供器（获取直链）。"""

    def __init__(
        self,
        config: Config,
        source: Source | None = None,
        playurl: PlayURLProvider | None = None,
    ) -> None:
        self._cfg = config
        self._default_source = source or TXSource()
        self._sources: dict[str, Source] = {"tx": self._default_source}
        if isinstance(self._default_source, WYSource):
            self._sources["wy"] = self._default_source
        self._playurl = playurl or ShiqianjiangProvider()

    def _get_source(self, name: str | None = None) -> Source:
        name = name or self._cfg.default_source or "tx"
        if name not in self._sources:
            cls = _SOURCES.get(name)
            if not cls:
                raise ValueError(f"未知音源: {name}，可选: {', '.join(_SOURCES)}")
            if cls is LocalSource:
                local_dirs = getattr(self._cfg, "local_dirs", [])
                if isinstance(local_dirs, str):
                    local_dirs = [d.strip() for d in local_dirs.split(",") if d.strip()]
                self._sources[name] = cls(local_dirs)
            else:
                self._sources[name] = cls()
        return self._sources[name]

    def close(self) -> None:
        for s in self._sources.values():
            s.close()

    def __enter__(self) -> "MusicClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    # -- source delegation ----------------------------------------------

    def search_music(self, query: str, page: int = 1, source: str | None = None) -> dict:
        return self._get_source(source).search_music(query, page)

    def search_album(self, query: str, page: int = 1, source: str | None = None) -> dict:
        return self._get_source(source).search_album(query, page)

    def get_music_info(self, songmid: str | None = None, song_id: int | None = None, source: str | None = None) -> MusicItem | None:
        return self._get_source(source).get_music_info(songmid=songmid, song_id=song_id)

    def get_album_info(self, album_mid: str, source: str | None = None) -> dict:
        return self._get_source(source).get_album_info(album_mid)

    def get_lyric(self, songmid: str, source: str | None = None) -> dict:
        return self._get_source(source).get_lyric(songmid)

    # -- play url -------------------------------------------------------

    def get_play_url(self, song: MusicItem, quality: str) -> str:
        if song.source == "local":
            return song.songmid  # songmid 存的是本地文件路径
        return self._playurl.get_play_url(song, quality, self._cfg.api_key, self._cfg.api_url)