"""QQ 音乐源。"""

import base64
import html
import json
import re
import time
from urllib.parse import quote

import httpx

from lxmusic.config import QQ_HEADERS, PAGE_SIZE
from lxmusic.models import AlbumItem, MusicItem
from lxmusic.sources import Source


def _parse_qualities(file: dict) -> dict[str, dict]:
    qualities: dict[str, dict] = {}
    if file.get("size_128mp3") and file["size_128mp3"] != 0:
        qualities["128k"] = {"size": file["size_128mp3"], "bitrate": 128000}
    if file.get("size_320mp3") and file["size_320mp3"] != 0:
        qualities["320k"] = {"size": file["size_320mp3"], "bitrate": 320000}
    if file.get("size_flac") and file["size_flac"] != 0:
        qualities["flac"] = {"size": file["size_flac"], "bitrate": 1411000}
    if file.get("size_hires") and file["size_hires"] != 0:
        qualities["hires"] = {"size": file["size_hires"], "bitrate": 1536000}
    return qualities


def _format_music_item(raw: dict) -> MusicItem:
    album = raw.get("album") or {}
    singers = raw.get("singer") or []
    return MusicItem(
        id=raw.get("id") or raw.get("songid", 0),
        songmid=raw.get("mid") or raw.get("songmid", ""),
        title=raw.get("title") or raw.get("songname") or raw.get("name", ""),
        artist=", ".join(s.get("name", "") for s in singers),
        album=album.get("title") or raw.get("albumname"),
        albummid=album.get("mid") or raw.get("albummid"),
        artwork=f"https://y.gtimg.cn/music/photo_new/T002R800x800M000{(album.get('mid') or raw.get('albummid'))}.jpg"
        if (album.get("mid") or raw.get("albummid"))
        else None,
        qualities=_parse_qualities(raw.get("file") or {}),
        source="tx",
    )


def _format_album_item(raw: dict) -> AlbumItem:
    return AlbumItem(
        id=raw.get("albumID") or raw.get("albumid", 0),
        album_mid=raw.get("albumMID") or raw.get("album_mid", ""),
        title=raw.get("albumName") or raw.get("album_name", ""),
        artist=raw.get("singerName") or raw.get("singer_name"),
        artwork=raw.get("albumPic")
        or (
            f"https://y.gtimg.cn/music/photo_new/T002R800x800M000{raw.get('albumMID') or raw.get('album_mid')}.jpg"
            if (raw.get("albumMID") or raw.get("album_mid"))
            else None
        ),
        date=raw.get("publicTime") or raw.get("pub_time"),
        singer_mid=raw.get("singerMID") or raw.get("singer_mid"),
        source="tx",
    )


class TXSource(Source):
    """QQ 音乐源。"""

    def __init__(self) -> None:
        self._client = httpx.Client(timeout=httpx.Timeout(15.0))

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "TXSource":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def get_audio_headers(self) -> dict[str, str]:
        return {"Referer": "https://y.qq.com"}

    # -- search ---------------------------------------------------------

    def _search_base(self, query: str, page: int, search_type: int) -> dict:
        type_map = {0: "song", 2: "album"}
        res = self._client.post(
            "https://u.y.qq.com/cgi-bin/musicu.fcg",
            json={
                "req_1": {
                    "method": "DoSearchForQQMusicDesktop",
                    "module": "music.search.SearchCgiService",
                    "param": {
                        "num_per_page": PAGE_SIZE,
                        "page_num": page,
                        "query": query,
                        "search_type": search_type,
                    },
                }
            },
            headers=QQ_HEADERS,
        )
        res.raise_for_status()
        data = res.json()
        items = data["req_1"]["data"]["body"][type_map[search_type]]["list"]
        return {"is_end": data["req_1"]["data"]["meta"]["sum"] <= page * PAGE_SIZE, "data": items}

    def search_music(self, query: str, page: int = 1) -> dict:
        result = self._search_base(query, page, 0)
        return {"is_end": result["is_end"], "data": [_format_music_item(it) for it in result["data"]]}

    def search_album(self, query: str, page: int = 1) -> dict:
        result = self._search_base(query, page, 2)
        return {"is_end": result["is_end"], "data": [_format_album_item(it) for it in result["data"]]}

    # -- detail ---------------------------------------------------------

    def _get_batch_qualities(self, song_list: list[dict]) -> dict[int, dict]:
        if not song_list:
            return {}
        try:
            res = self._client.post(
                "https://u.y.qq.com/cgi-bin/musicu.fcg",
                json={
                    "comm": {"ct": "19", "cv": "1859", "uin": "0"},
                    "req": {
                        "module": "music.trackInfo.UniformRuleCtrl",
                        "method": "CgiGetTrackInfo",
                        "param": {
                            "types": [1] * len(song_list),
                            "ids": [it.get("songid") or it.get("id", 0) for it in song_list],
                            "ctx": 0,
                        },
                    },
                },
                headers=QQ_HEADERS,
            )
            tracks = res.json().get("req", {}).get("data", {}).get("tracks", [])
            return {t["id"]: _parse_qualities(t.get("file", {})) for t in tracks}
        except Exception:
            return {}

    def get_music_info(self, songmid: str | None = None, song_id: int | None = None) -> MusicItem | None:
        if not songmid and not song_id:
            raise ValueError("至少提供 songmid 或 song_id")
        try:
            res = self._client.post(
                "https://u.y.qq.com/cgi-bin/musicu.fcg",
                json={
                    "comm": {"ct": "19", "cv": "1859", "uin": "0"},
                    "req": {
                        "module": "music.trackInfo.UniformRuleCtrl",
                        "method": "CgiGetTrackInfo",
                        "param": {
                            "types": [1],
                            "ids": [int(song_id)] if song_id and str(song_id).isdigit() else [0],
                            "mids": [str(songmid)] if songmid else [],
                            "ctx": 0,
                        },
                    },
                },
                headers=QQ_HEADERS,
            )
            tracks = res.json().get("req", {}).get("data", {}).get("tracks", [])
            if not tracks:
                return None
            return _format_music_item(tracks[0])
        except Exception:
            return None

    def get_album_info(self, album_mid: str) -> dict:
        payload = json.dumps({
            "comm": {"ct": 24, "cv": 10000},
            "albumSonglist": {
                "method": "GetAlbumSongList",
                "param": {"albumMid": album_mid, "albumID": 0, "begin": 0, "num": 999, "order": 2},
                "module": "music.musichallAlbum.AlbumSongList",
            },
        })
        url = f"https://u.y.qq.com/cgi-bin/musicu.fcg?g_tk=5381&format=json&inCharset=utf8&outCharset=utf-8&data={quote(payload, safe='')}"
        res = self._client.get(url, headers=QQ_HEADERS)
        res.raise_for_status()
        data = res.json()
        song_list = [s["songInfo"] for s in data["albumSonglist"]["data"]["songList"]]
        quality_info = self._get_batch_qualities(song_list)
        music_list = []
        for s in song_list:
            item = _format_music_item(s)
            sid = item.id
            if sid in quality_info:
                item.qualities = quality_info[sid]
            music_list.append(item)
        return {"music_list": music_list}

    def get_lyric(self, songmid: str) -> dict:
        try:
            ts = str(int(time.time() * 1000))
            url = (
                f"https://c.y.qq.com/lyric/fcgi-bin/fcg_query_lyric_new.fcg"
                f"?songmid={songmid}&pcachetime={ts}&g_tk=5381&loginUin=0&hostUin=0"
                f"&inCharset=utf8&outCharset=utf-8&notice=0&platform=yqq&needNewCode=0"
            )
            res = self._client.get(url, headers=QQ_HEADERS)
            text = res.text
            text = re.sub(r"^(callback|MusicJsonCallback|jsonCallback)\(|\);?\s*$", "", text)
            data = json.loads(text)

            raw_lrc = ""
            translation = ""
            if data.get("lyric"):
                try:
                    raw_lrc = html.unescape(base64.b64decode(data["lyric"]).decode("utf-8"))
                except Exception:
                    raw_lrc = data["lyric"]
            if data.get("trans"):
                try:
                    translation = html.unescape(base64.b64decode(data["trans"]).decode("utf-8"))
                except Exception:
                    translation = data["trans"]
            return {"raw_lrc": raw_lrc, "translation": translation}
        except Exception:
            return {"raw_lrc": "", "translation": ""}