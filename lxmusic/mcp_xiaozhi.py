"""MCP xiaozhi 兼容 Server — musicPlayer 工具 + resource://read_from_http 音频流。

协议参考: https://github.com/hackers365/mcp_audio_server

策略：musicPlayer 只返回 source+id，resource/read 时惰性解析播放地址 + LRU 缓存 5 分钟。
"""

import asyncio
import base64
import sys
import time
import logging
from typing import Any

import httpx

import mcp.server as server
import mcp.server.models as models
import mcp.types as types

from lxmusic.client import MusicClient
from lxmusic.config import Config
from lxmusic.models import MusicItem

logger = logging.getLogger("lxmusic.xiaozhi")

_MAX_CACHE = 64
_TTL = 300  # 5 分钟


class _PlayURLCache:
    """简单的 LRU + TTL 缓存 (source:id → url)。"""

    def __init__(self, maxsize: int = _MAX_CACHE, ttl: int = _TTL) -> None:
        self._maxsize = maxsize
        self._ttl = ttl
        self._data: dict[str, tuple[float, str]] = {}  # key → (expire_at, url)
        self._order: list[str] = []

    def get(self, key: str) -> str | None:
        entry = self._data.get(key)
        if not entry:
            return None
        expire_at, url = entry
        if time.monotonic() > expire_at:
            self._data.pop(key, None)
            return None
        # 移到末尾（最近使用）
        self._order = [k for k in self._order if k != key] + [key]
        return url

    def put(self, key: str, url: str) -> None:
        now = time.monotonic()
        if key in self._data:
            self._data[key] = (now + self._ttl, url)
            self._order = [k for k in self._order if k != key] + [key]
            return
        # LRU 淘汰
        while len(self._data) >= self._maxsize:
            old = self._order.pop(0)
            self._data.pop(old, None)
        self._data[key] = (now + self._ttl, url)
        self._order.append(key)

    def resolve(
        self, client: MusicClient, source: str, song_id_or_mid: str
    ) -> tuple[str, str] | None:
        """获取播放 URL（缓存命中直接返回，否则解析后缓存）。

        Returns:
            (play_url_or_path, source) — source 用于 caller 选择 Referer 或 file:// 读取。
        """
        key = f"{source}:{song_id_or_mid}"
        cached = self.get(key)
        if cached:
            return cached, source
        try:
            song = client.get_music_info(
                songmid=song_id_or_mid if not song_id_or_mid.isdigit() else None,
                song_id=int(song_id_or_mid) if song_id_or_mid.isdigit() else None,
                source=source,
            )
            if not song:
                return None
            url = client.get_play_url(song, "128k")
            self.put(key, url)
            return url, source
        except Exception:
            return None


_cache = _PlayURLCache()


def _make_tag(source: str, sid: str) -> str:
    return f"{source}_{sid}"


def create_xiaozhi_server(cfg: Config, client: MusicClient):
    app = server.Server("lxmusic-xiaozhi")

    @app.list_tools()
    async def handle_list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name="musicPlayer",
                description="搜索音乐，返回 ResourceLink 列表",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "搜索关键词"},
                    },
                    "required": ["query"],
                },
            )
        ]

    @app.call_tool()
    async def handle_call_tool(
        name: str, arguments: dict
    ) -> list[types.TextContent | types.EmbeddedResource]:
        if name != "musicPlayer":
            raise ValueError(f"Unknown tool: {name}")

        query = arguments.get("query", "")
        result = client.search_music(query, 1)
        items: list[types.TextContent | types.EmbeddedResource] = []

        for song in result["data"][:10]:
            sid = str(song.id)
            tag = _make_tag(song.source, sid)
            items.append(
                types.EmbeddedResource(
                    type="resource",
                    resource=types.Resource(
                        uri=f"resource://read_{tag}",
                        name=f"{song.title} - {song.artist}",
                        description=f"source={song.source},id={sid}",
                        mimeType="audio/mpeg",
                    ),
                )
            )

        return items or [types.TextContent(type="text", text="[]")]

    @app.list_resources()
    async def handle_list_resources() -> list[types.Resource]:
        return []

    @app.read_resource()
    async def handle_read_resource(
        uri: str,
    ) -> str:
        # 从 URI 解析 source 和 id: resource://read_tx_102065756
        tag = uri.replace("resource://read_", "", 1)
        if "_" not in tag:
            return base64.b64encode(b"[DONE]").decode()
        source, sid = tag.split("_", 1)

        # 惰性解析播放地址（LRU 缓存 5 分钟）
        resolved = _cache.resolve(client, source, sid)
        if not resolved:
            return base64.b64encode(b"[DONE]").decode()
        play_url, actual_source = resolved

        try:
            # 本地文件源直接读取
            if actual_source == "local":
                from pathlib import Path
                p = Path(play_url)
                if not p.exists():
                    return base64.b64encode(b"[DONE]").decode()
                data = p.read_bytes()
                return base64.b64encode(data).decode() if data else base64.b64encode(b"[DONE]").decode()

            # 网络源 — 从 Source 实现获取播放 CDN 请求头
            try:
                src = client._get_source(actual_source)
                headers = dict(src.get_audio_headers())
            except Exception:
                headers = {}
            headers.setdefault("User-Agent", "Mozilla/5.0")

            with httpx.Client(timeout=30.0) as hc:
                resp = hc.get(play_url, headers=headers, follow_redirects=True)
                resp.raise_for_status()
                _data = resp.content
                return base64.b64encode(_data).decode()
        except Exception:
            return base64.b64encode(b"[DONE]").decode()

    return app


def run_xiaozhi_server(wss_url: str | None = None) -> None:
    """启动 xiaozhi MCP server。

    Args:
        wss_url: 如果提供，通过 WSS 注册到小智而不是走 stdio。
    """
    import mcp.server.stdio

    logging.basicConfig(
        level=logging.INFO,
        format="[xiaozhi] %(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )

    cfg = Config()
    client = MusicClient(cfg)
    app = create_xiaozhi_server(cfg, client)

    logger.info(
        "音源=%s 音质=128k API=%s 密钥=%s",
        cfg.default_source,
        cfg.api_url,
        "已设置" if cfg.api_key else "未设置",
    )

    async def _entry():
        nonlocal wss_url
        logger.info("xiaozhi server 启动中...")
        if wss_url:
            logger.info("使用 WSS 模式: %s", wss_url[:60] + "..." if len(wss_url) > 60 else wss_url)
            await _run_wss(app, wss_url)
        else:
            logger.info("使用 stdio 模式")
            async with mcp.server.stdio.stdio_server() as (read, write):
                logger.info("stdio 已就绪，等待客户端连接")
                await app.run(
                    read,
                    write,
                    models.InitializationOptions(
                        server_name="lxmusic-xiaozhi",
                        server_version="0.1.0",
                        capabilities=types.ServerCapabilities(),
                    ),
                )

    asyncio.run(_entry())


async def _run_wss(app: server.Server, wss_url: str) -> None:
    """通过 WebSocket 注册到小智 MCP 代理。

    启动 stdio MCP server 子进程，与 WSS 双向管道转发。
    """
    import websockets

    backoff = 1
    MAX_BACKOFF = 600

    async def _pipe_ws_to_stdin(ws, stdin):
        try:
            async for msg in ws:
                stdin.write((msg + "\n").encode())
                await stdin.drain()
        except Exception:
            pass

    async def _pipe_stdout_to_ws(stdout, ws):
        try:
            while True:
                line = await stdout.readline()
                if not line:
                    break
                await ws.send(line.decode().rstrip())
        except Exception:
            pass

    while True:
        try:
            logger.info("正在连接 WSS: %s...", wss_url[:60] + "..." if len(wss_url) > 60 else wss_url)
            async with websockets.connect(wss_url) as ws:
                logger.info("WSS 已连接")
                backoff = 1
                proc = await asyncio.create_subprocess_exec(
                    sys.executable, "-c",
                    "from lxmusic.main import main; main()", "xiaozhi",
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=None,
                )
                logger.info("子进程已启动 (PID %d)", proc.pid)
                if not proc.stdin or not proc.stdout:
                    continue
                await asyncio.gather(
                    _pipe_ws_to_stdin(ws, proc.stdin),
                    _pipe_stdout_to_ws(proc.stdout, ws),
                )
        except (OSError, asyncio.TimeoutError) as e:
            logger.warning("WSS 连接失败: %s, %ds 后重试...", e, backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, MAX_BACKOFF)
