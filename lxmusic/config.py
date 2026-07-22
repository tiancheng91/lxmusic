"""配置加载：环境变量 > YAML 配置文件 > 内置默认值。"""

import os
from pathlib import Path

import yaml

CONFIG_DIR = Path.home() / ".config" / "lxmusic"

QUALITY_EXT = {"128k": ".mp3", "320k": ".mp3", "flac": ".flac", "hires": ".flac"}
SUPPORTED_QUALITIES = ["128k", "320k", "flac", "hires"]
PAGE_SIZE = 20

QQ_HEADERS = {
    "Referer": "https://y.qq.com",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Cookie": "uin=",
}


class Config:
    """配置加载：环境变量 > YAML 配置文件 > 内置默认值。首次运行自动落盘。"""

    _env_map = {
        "api_url": "LX_MUSIC_API_URL",
        "api_key": "LX_MUSIC_API_KEY",
        "default_quality": "LX_MUSIC_DEFAULT_QUALITY",
        "default_source": "LX_MUSIC_DEFAULT_SOURCE",
        "local_dirs": "LX_MUSIC_LOCAL_DIRS",
        "library_dir": "LX_MUSIC_LIBRARY_DIR",
        "playlist_dir": "LX_MUSIC_PLAYLIST_DIR",
        "cache_dir": "LX_MUSIC_CACHE_DIR",
    }

    def __init__(self) -> None:
        self._data: dict[str, str] = {}
        self._load_yaml()
        self._load_env()
        self._set_defaults()

    def _load_yaml(self) -> None:
        yaml_path = CONFIG_DIR / "config.yaml"
        if yaml_path.exists():
            try:
                file_data = yaml.safe_load(yaml_path.read_text())
                if isinstance(file_data, dict):
                    self._data.update(file_data)
            except Exception:
                pass

    def _load_env(self) -> None:
        for key, env_var in self._env_map.items():
            val = os.environ.get(env_var)
            if val:
                self._data[key] = val

    def _set_defaults(self) -> None:
        base = Path.home() / ".config" / "lxmusic"
        self._data.setdefault("api_url", "https://source.shiqianjiang.cn/api/music")
        self._data.setdefault("default_quality", "320k")
        self._data.setdefault("default_source", "tx")
        self._data.setdefault("local_dirs", str(base / "library"))
        self._data.setdefault("library_dir", str(base / "library"))
        self._data.setdefault("playlist_dir", str(base / "playlists"))
        self._data.setdefault("cache_dir", str(base / "cache"))

    def save_defaults(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        yaml_path = CONFIG_DIR / "config.yaml"
        if not yaml_path.exists():
            base = Path.home() / ".config" / "lxmusic"
            defaults = {
                "api_url": "https://source.shiqianjiang.cn/api/music",
                "default_quality": "320k",
                "default_source": "tx",
                "library_dir": str(base / "library"),
                "playlist_dir": str(base / "playlists"),
                "cache_dir": str(base / "cache"),
            }
            yaml_path.write_text(yaml.dump(defaults, default_flow_style=False, allow_unicode=True))

    def __getattr__(self, name: str) -> str:
        if name in self._data:
            return self._data[name]
        if name == "api_key":
            return ""
        raise AttributeError(name)

    def set(self, key: str, value: str) -> None:
        """写入配置项到 config.yaml 并刷新内存。"""
        yaml_path = CONFIG_DIR / "config.yaml"
        data: dict = {}
        if yaml_path.exists():
            data = yaml.safe_load(yaml_path.read_text()) or {}
        # 如果 value 是空字符串则删除该项
        if not value:
            data.pop(key, None)
        else:
            data[key] = value
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        yaml_path.write_text(yaml.dump(data, default_flow_style=False, allow_unicode=True))
        # 刷新内存
        self._data[key] = value
