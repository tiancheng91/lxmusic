"""lxmusic 单元测试 — 纯函数。"""

from pathlib import Path

import pytest

from lxmusic.sources.tx import _parse_qualities, _format_music_item
from lxmusic.storage import PlaylistStore


class TestParseQualities:
    def test_empty(self):
        assert _parse_qualities({}) == {}

    def test_all_qualities(self):
        file = {
            "size_128mp3": 5000000,
            "size_320mp3": 10000000,
            "size_flac": 25000000,
            "size_hires": 50000000,
        }
        result = _parse_qualities(file)
        assert "128k" in result
        assert "320k" in result
        assert "flac" in result
        assert "hires" in result
        assert result["128k"]["bitrate"] == 128000
        assert result["320k"]["bitrate"] == 320000
        assert result["flac"]["bitrate"] == 1411000
        assert result["hires"]["bitrate"] == 1536000

    def test_zero_size_skipped(self):
        file = {"size_128mp3": 0, "size_320mp3": 10000000}
        result = _parse_qualities(file)
        assert "128k" not in result
        assert "320k" in result


class TestFormatMusicItem:
    def test_basic(self):
        raw = {
            "id": 123,
            "mid": "abc123",
            "title": "测试歌曲",
            "singer": [{"name": "歌手A"}, {"name": "歌手B"}],
            "album": {"title": "测试专辑", "mid": "alb001"},
            "file": {"size_320mp3": 10000000},
        }
        item = _format_music_item(raw)
        assert item.id == 123
        assert item.songmid == "abc123"
        assert item.title == "测试歌曲"
        assert item.artist == "歌手A, 歌手B"
        assert item.album == "测试专辑"
        assert item.albummid == "alb001"
        assert "320k" in item.qualities

    def test_no_file(self):
        raw = {"id": 1, "mid": "x", "title": "x", "singer": []}
        item = _format_music_item(raw)
        assert item.qualities == {}


class TestPlaylistStore:
    def test_create_and_get(self, tmp_path: Path) -> None:
        store = PlaylistStore(tmp_path / "playlists")
        store.create("coding")
        data = store.get("coding")
        assert data["name"] == "coding"
        assert data["tracks"] == []

    def test_create_duplicate(self, tmp_path: Path) -> None:
        store = PlaylistStore(tmp_path / "playlists")
        store.create("coding")
        with pytest.raises(FileExistsError):
            store.create("coding")

    def test_get_nonexistent(self, tmp_path: Path) -> None:
        from lxmusic.errors import PlaylistNotFoundError
        store = PlaylistStore(tmp_path / "playlists")
        with pytest.raises(PlaylistNotFoundError):
            store.get("nonexistent")

    def test_add_auto_create(self, tmp_path: Path) -> None:
        store = PlaylistStore(tmp_path / "playlists")
        track = {"id": 1, "title": "七里香", "artist": "周杰伦", "path": "/tmp/a.mp3"}
        store.add("test", track)
        data = store.get("test")
        assert len(data["tracks"]) == 1
        assert data["tracks"][0]["title"] == "七里香"

    def test_add_append(self, tmp_path: Path) -> None:
        store = PlaylistStore(tmp_path / "playlists")
        store.create("test")
        store.add("test", {"id": 1, "title": "A", "artist": "X", "path": "/a.mp3"})
        store.add("test", {"id": 2, "title": "B", "artist": "Y", "path": "/b.mp3"})
        data = store.get("test")
        assert len(data["tracks"]) == 2

    def test_list_all(self, tmp_path: Path) -> None:
        store = PlaylistStore(tmp_path / "playlists")
        assert store.list_all() == []
        store.create("a")
        store.create("b")
        assert store.list_all() == ["a", "b"]

    def test_export_m3u(self, tmp_path: Path) -> None:
        store = PlaylistStore(tmp_path / "playlists")
        store.add("test", {"id": 1, "title": "七里香", "artist": "周杰伦", "path": "/music/a.mp3"})
        dest = tmp_path / "test.m3u"
        result = store.export_m3u("test", dest)
        assert result == dest
        content = dest.read_text()
        assert "#EXTM3U" in content
        assert "周杰伦 - 七里香" in content
        assert "/music/a.mp3" in content