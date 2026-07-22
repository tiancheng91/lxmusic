"""本地音乐源 — 扫描目录中的音频文件及歌单 YAML。"""

import hashlib
import json
import os
import random
from pathlib import Path

import yaml

from lxmusic.config import SUPPORTED_QUALITIES
from lxmusic.models import AlbumItem, MusicItem
from lxmusic.sources import Source

AUDIO_EXT = {".mp3", ".flac", ".wav", ".m4a", ".ogg", ".wma"}


class LocalSource(Source):
    """本地目录音乐源。

    配置 local_dirs 为音频文件目录列表，搜索时按文件名匹配。
    同时扫描目录下的 .yaml 文件，解析为歌单，匹配歌单名时返回曲目。
    """

    def __init__(self, dirs: list[str] | None = None) -> None:
        self._dirs = [Path(d).expanduser().resolve() for d in (dirs or [])]

    def get_audio_headers(self) -> dict[str, str]:
        return {}

    def close(self) -> None:
        pass

    def _scan_files(self) -> list[Path]:
        files = []
        for d in self._dirs:
            if not d.is_dir():
                continue
            for f in d.rglob("*"):
                if f.suffix.lower() in AUDIO_EXT:
                    files.append(f)
        return files

    def _parse_playlist_yaml(self, path: Path) -> tuple[str, list[dict]] | None:
        """解析歌单 YAML，返回 (name, tracks)，非歌单格式返回 None。"""
        try:
            data = yaml.safe_load(path.read_text())
            if isinstance(data, dict) and data.get("name") and isinstance(data.get("tracks"), list):
                return data["name"], data["tracks"]
        except Exception:
            pass
        return None

    def _scan_playlists(self) -> list[tuple[str, list[dict]]]:
        """扫描目录下的 YAML 文件，返回 [(name, tracks), ...]。"""
        result = []
        for d in self._dirs:
            if not d.is_dir():
                continue
            for f in d.rglob("*.yaml"):
                if f.is_file():
                    parsed = self._parse_playlist_yaml(f)
                    if parsed is not None:
                        result.append(parsed)
        return result

    def _file_id(self, path: str) -> int:
        return int(hashlib.md5(path.encode()).hexdigest()[:12], 16) % (10**10)

    def _path_to_music_item(self, path: Path, idx: int) -> MusicItem:
        file_id = self._file_id(str(path))
        return MusicItem(
            id=file_id,
            songmid=str(path),
            title=path.stem,
            artist="",
            album=path.parent.name,
            artwork=None,
            qualities={"128k": {"size": path.stat().st_size, "bitrate": 128000}},
            source="local",
        )

    def _track_to_music_item(self, track: dict) -> MusicItem:
        path = track.get("path", "")
        p = Path(path)
        if p.exists() and p.suffix.lower() in AUDIO_EXT:
            file_id = self._file_id(path)
            qualities = {"128k": {"size": p.stat().st_size, "bitrate": 128000}}
        else:
            file_id = self._file_id(path)
            qualities = {}
        return MusicItem(
            id=file_id,
            songmid=path,
            title=track.get("title", p.stem),
            artist=track.get("artist", ""),
            album="",
            artwork=None,
            qualities=qualities,
            source="local",
        )

    def search_music(self, query: str, page: int = 1) -> dict:
        q = query.lower()
        matched = []

        # 按文件名匹配音频文件
        for f in self._scan_files():
            if q in f.stem.lower():
                matched.append(self._path_to_music_item(f, len(matched)))

        random.shuffle(matched)

        offset = (page - 1) * 20
        return {"is_end": len(matched) <= offset + 20, "data": matched[offset : offset + 20]}

    def search_album(self, query: str, page: int = 1) -> dict:
        """搜索本地歌单 YAML，匹配 name 字段。"""
        q = query.lower()
        matched = []
        for name, tracks in self._scan_playlists():
            if q in name.lower():
                matched.append(AlbumItem(
                    id=self._file_id(name),
                    album_mid=name,
                    title=name,
                    artist="",
                    source="local",
                ))
        return {"is_end": True, "data": matched}

    def get_album_info(self, album_mid: str) -> dict:
        """按歌单名查找 YAML，返回曲目列表。"""
        for name, tracks in self._scan_playlists():
            if name == album_mid:
                return {"music_list": [self._track_to_music_item(t) for t in tracks]}
        return {"music_list": []}

    def get_music_info(self, songmid: str | None = None, song_id: int | None = None) -> MusicItem | None:
        if songmid:
            p = Path(songmid)
            if p.exists() and p.suffix.lower() in AUDIO_EXT:
                return self._path_to_music_item(p, 0)
            return None
        if song_id is not None:
            for f in self._scan_files():
                if self._file_id(str(f)) == song_id:
                    return self._path_to_music_item(f, 0)
        return None

    def get_lyric(self, songmid: str) -> dict:
        return {"raw_lrc": "", "translation": ""}