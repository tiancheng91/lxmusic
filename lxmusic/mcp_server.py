"""MCP Server — 暴露搜索/播放工具。"""

from dataclasses import asdict
from typing import Any

from lxmusic.client import MusicClient
from lxmusic.config import Config
from lxmusic.errors import LXMusicError


def create_mcp_server(
    cfg: Config,
    client: MusicClient,
):
    """创建 FastMCP stdio server。"""
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("lxmusic")

    def _err(error: str, message: str) -> dict:
        return {"ok": False, "error": error, "message": message}

    def _ok(**kwargs: Any) -> dict:
        return {"ok": True, **kwargs}

    @mcp.tool()
    def search_music(query: str, page: int = 1, source: str = "") -> dict:
        try:
            result = client.search_music(query, page, source=source or None)
            return _ok(is_end=result["is_end"], data=[asdict(s) for s in result["data"]])
        except LXMusicError as e:
            return _err(type(e).__name__, str(e))

    @mcp.tool()
    def search_album(query: str, page: int = 1, source: str = "") -> dict:
        try:
            result = client.search_album(query, page, source=source or None)
            return _ok(is_end=result["is_end"], data=[asdict(a) for a in result["data"]])
        except LXMusicError as e:
            return _err(type(e).__name__, str(e))

    @mcp.tool()
    def play_music(
        song_id: int | None = None,
        songmid: str | None = None,
        quality: str = "320k",
        source: str = "",
    ) -> dict:
        try:
            if not song_id and not songmid:
                return _err("invalid_args", "请提供 song_id 或 songmid")
            song = client.get_music_info(songmid=songmid, song_id=song_id, source=source or None)
            if not song:
                return _err("song_not_found", "未找到歌曲")
            url = client.get_play_url(song, quality)
            result = {"url": url, "quality": quality, "song": asdict(song)}
            try:
                lyric = client.get_lyric(song.songmid)
                if lyric.get("raw_lrc"):
                    result["lyric"] = lyric["raw_lrc"]
            except Exception:
                pass
            return _ok(**result)
        except LXMusicError as e:
            return _err(type(e).__name__.replace("Error", "").lower(), str(e))

    return mcp