"""网易云音乐源。"""

import json
from urllib.parse import quote

import httpx

from lxmusic.config import PAGE_SIZE
from lxmusic.models import AlbumItem, MusicItem
from lxmusic.sources import Source

WY_HEADERS = {
    "Referer": "https://music.163.com",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}


def _wy_parse_privilege(privilege: dict | None) -> dict[str, dict]:
    qualities: dict[str, dict] = {}
    if not privilege:
        return qualities
    pl = privilege.get("pl", 0)
    if pl > 0:
        qualities["flac"] = {"size": 0, "bitrate": 1411000}
    dl = privilege.get("dl", 0)
    if dl > 0:
        qualities["hires"] = {"size": 0, "bitrate": 1536000}
    st = privilege.get("st", 0)
    if st > 0:
        qualities["320k"] = {"size": 0, "bitrate": 320000}
    qualities["128k"] = {"size": 0, "bitrate": 128000}
    return qualities


def _wy_format_music_item(raw: dict) -> MusicItem:
    album = raw.get("al") or raw.get("album") or {}
    artists = raw.get("ar") or raw.get("artists") or []
    return MusicItem(
        id=raw.get("id", 0),
        songmid=str(raw.get("id", 0)),
        title=raw.get("name", ""),
        artist=", ".join(a.get("name", "") for a in artists),
        album=album.get("name", ""),
        albummid=str(album.get("id", "")),
        artwork=album.get("picUrl") or None,
        qualities=_wy_parse_privilege(raw.get("privilege")),
        source="wy",
    )


def _wy_format_album_item(raw: dict) -> AlbumItem:
    artist = raw.get("artist") or raw.get("artists") or {}
    if isinstance(artist, list):
        artist = artist[0] if artist else {}
    return AlbumItem(
        id=raw.get("id", 0),
        album_mid=str(raw.get("id", 0)),
        title=raw.get("name", ""),
        artist=artist.get("name", "") if isinstance(artist, dict) else "",
        artwork=raw.get("picUrl") or raw.get("coverImgUrl"),
        date=raw.get("publishTime"),
        source="wy",
    )


class WYSource(Source):
    """网易云音乐源。"""

    def __init__(self) -> None:
        self._client = httpx.Client(timeout=httpx.Timeout(15.0))

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "WYSource":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def get_audio_headers(self) -> dict[str, str]:
        return {"Referer": "https://music.163.com"}

    # -- search ---------------------------------------------------------

    def search_music(self, query: str, page: int = 1) -> dict:
        offset = (page - 1) * PAGE_SIZE
        res = self._client.post(
            "https://music.163.com/api/cloudsearch/pc",
            data={"s": query, "offset": offset, "limit": PAGE_SIZE, "type": 1},
            headers=WY_HEADERS,
        )
        res.raise_for_status()
        data = res.json()
        songs = (data.get("result") or {}).get("songs", [])
        return {
            "is_end": len(songs) < PAGE_SIZE,
            "data": [_wy_format_music_item(s) for s in songs],
        }

    def search_album(self, query: str, page: int = 1) -> dict:
        offset = (page - 1) * PAGE_SIZE
        res = self._client.post(
            "https://music.163.com/api/cloudsearch/pc",
            data={"s": query, "offset": offset, "limit": PAGE_SIZE, "type": 10},
            headers=WY_HEADERS,
        )
        res.raise_for_status()
        data = res.json()
        albums = (data.get("result") or {}).get("albums", [])
        return {
            "is_end": len(albums) < PAGE_SIZE,
            "data": [_wy_format_album_item(a) for a in albums],
        }

    # -- detail ---------------------------------------------------------

    def get_music_info(self, songmid: str | None = None, song_id: int | None = None) -> MusicItem | None:
        sid = song_id or (int(songmid) if songmid and songmid.isdigit() else 0)
        if not sid:
            return None
        try:
            res = self._client.get(
                "https://music.163.com/api/v3/song/detail",
                params={"c": json.dumps([{"id": sid}]), "ids": f"[{sid}]"},
                headers=WY_HEADERS,
            )
            res.raise_for_status()
            data = res.json()
            songs = data.get("songs", [])
            if not songs:
                return None
            return _wy_format_music_item(songs[0])
        except Exception:
            return None

    def get_album_info(self, album_mid: str) -> dict:
        album_id = int(album_mid) if album_mid.isdigit() else 0
        if not album_id:
            return {"music_list": []}
        try:
            res = self._client.get(
                f"https://music.163.com/api/album/{album_id}",
                headers=WY_HEADERS,
            )
            res.raise_for_status()
            data = res.json()
            songs = data.get("songs", [])
            return {"music_list": [_wy_format_music_item(s) for s in songs]}
        except Exception:
            return {"music_list": []}

    def get_lyric(self, songmid: str) -> dict:
        sid = int(songmid) if songmid.isdigit() else 0
        if not sid:
            return {"raw_lrc": "", "translation": ""}
        try:
            res = self._client.get(
                "https://music.163.com/api/song/lyric",
                params={"id": sid, "lv": 1, "kv": 1, "tv": -1},
                headers=WY_HEADERS,
            )
            res.raise_for_status()
            data = res.json()
            raw_lrc = (data.get("lrc") or {}).get("lyric", "")
            return {"raw_lrc": raw_lrc, "translation": ""}
        except Exception:
            return {"raw_lrc": "", "translation": ""}