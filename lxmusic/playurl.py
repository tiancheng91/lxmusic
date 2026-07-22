"""播放链接提供器 — 从第三方后端获取音频直链。"""

from abc import ABC, abstractmethod

import httpx

from lxmusic.config import QQ_HEADERS
from lxmusic.errors import (
    ApiKeyInvalidError,
    NetworkError,
    QualityNotAvailableError,
    RateLimitedError,
    SongNotFoundError,
)
from lxmusic.models import MusicItem


class PlayURLProvider(ABC):
    """播放链接提供器抽象接口。"""

    @abstractmethod
    def get_play_url(self, song: MusicItem, quality: str, api_key: str, api_url: str) -> str: ...


class ShiqianjiangProvider(PlayURLProvider):
    """shiqianjiang.cn 第三方后端提供播放链接。"""

    def get_play_url(self, song: MusicItem, quality: str, api_key: str, api_url: str) -> str:
        song_id = song.songmid or str(song.id)
        if song.qualities and quality not in song.qualities:
            raise QualityNotAvailableError(f"该歌曲不支持 {quality} 音质")

        headers = {
            "User-Agent": QQ_HEADERS["User-Agent"],
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if api_key:
            headers["X-API-Key"] = api_key

        with httpx.Client(timeout=httpx.Timeout(15.0)) as client:
            res = client.get(
                f"{api_url}/url",
                params={"source": song.source, "songId": song_id, "quality": quality},
                headers=headers,
            )
            res.raise_for_status()
            data = res.json()
            code = data.get("code")
            if code == 200 and data.get("url"):
                return data["url"]
            if code == 403:
                raise ApiKeyInvalidError("API 密钥无效或已过期")
            if code == 429:
                raise RateLimitedError("请求过于频繁，请稍后再试")
            if code == 404:
                raise SongNotFoundError(f"歌曲不存在或已下架: {song_id}")
            raise NetworkError(f"获取播放链接失败: {data.get('message') or data.get('msg') or '未知错误'}")