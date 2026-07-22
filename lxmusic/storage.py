"""下载工具函数 & 歌单存储。"""

import json
from pathlib import Path

import httpx
import yaml

from lxmusic.config import QUALITY_EXT
from lxmusic.errors import PlaylistNotFoundError


def _download_file(url: str, dest: Path, progress_cb=None) -> Path:
    """从 URL 流式下载到目标路径，下载过程中用 .tmp 后缀，完成后原子重命名。

    progress_cb: 可选回调 fn(current, total) 用于显示进度。
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    with httpx.stream("GET", url, timeout=httpx.Timeout(120.0), follow_redirects=True, headers={"Referer": "https://y.qq.com"}) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        downloaded = 0
        with open(tmp, "wb") as f:
            for chunk in r.iter_bytes(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)
                if progress_cb:
                    progress_cb(downloaded, total)
    tmp.rename(dest)
    return dest


def sanitize(name: str) -> str:
    import re
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip(" .")


PLAYLIST_TRACK_FMT = "  - {track_json}\n"


class PlaylistStore:
    """歌单 YAML 存储。"""

    def __init__(self, playlist_dir: str | Path) -> None:
        self._dir = Path(playlist_dir)

    def _path(self, name: str) -> Path:
        return (self._dir / name).with_suffix(".yaml")

    def _load(self, name: str) -> dict:
        path = self._path(name)
        if not path.exists():
            raise PlaylistNotFoundError(f"歌单不存在: {name}")
        data = yaml.safe_load(path.read_text()) or {}
        if data.get("tracks") is None:
            data["tracks"] = []
        return data

    def _dump(self, name: str, data: dict) -> None:
        path = self._path(name)
        self._dir.mkdir(parents=True, exist_ok=True)
        lines = [f"name: {name}\n", "tracks:\n"]
        for t in data.get("tracks", []):
            lines.append(PLAYLIST_TRACK_FMT.format(track_json=json.dumps(t, ensure_ascii=False)))
        path.write_text("".join(lines))

    def create(self, name: str) -> Path:
        """创建空歌单。已存在则报错。"""
        path = self._path(name)
        if path.exists():
            raise FileExistsError(f"歌单已存在: {name}")
        self._dir.mkdir(parents=True, exist_ok=True)
        path.write_text(f"name: {name}\ntracks:\n")
        return path

    def get(self, name: str) -> dict:
        """加载歌单，返回 {"name": ..., "tracks": [...]}。"""
        return self._load(name)

    def add(self, name: str, track: dict) -> None:
        """追加 track 到歌单。歌单不存在时自动创建。"""
        try:
            data = self._load(name)
        except PlaylistNotFoundError:
            data = {"name": name, "tracks": []}
        data["tracks"].append(track)
        self._dump(name, data)

    def list_all(self) -> list[str]:
        """列出所有歌单名（按文件名排序）。"""
        if not self._dir.exists():
            return []
        return sorted(sorted(
            p.stem for p in self._dir.iterdir() if p.suffix == ".yaml"
        ))

    def export_m3u(self, name: str, dest: Path) -> Path:
        """导出 M3U8 格式歌单文件。"""
        data = self._load(name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        lines = ["#EXTM3U\n"]
        for t in data["tracks"]:
            extinf = f"#EXTINF:-1,{t.get('artist', '')} - {t['title']}\n"
            lines.append(extinf)
            lines.append(f"{t['path']}\n")
        dest.write_text("".join(lines), encoding="utf-8")
        return dest