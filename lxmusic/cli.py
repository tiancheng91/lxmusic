"""CLI — click 命令组。"""

import json
from dataclasses import asdict
from pathlib import Path

import click
import yaml

from lxmusic.config import Config, QUALITY_EXT, SUPPORTED_QUALITIES
from lxmusic.client import MusicClient
from lxmusic.errors import LXMusicError, QualityNotAvailableError, SongNotFoundError
from lxmusic.models import AlbumItem, MusicItem
from lxmusic.storage import _download_file, sanitize, PlaylistStore


def _resolve_song_id(value: str) -> tuple[int | None, str | None]:
    try:
        return int(value), None
    except ValueError:
        return None, value


def _format_music_table(songs: list[MusicItem]) -> str:
    lines = []
    for s in songs:
        qs = ", ".join(s.qualities.keys()) if s.qualities else "?"
        lines.append(f"  {s.id:>10}  {s.songmid:<16}  {s.title[:20]:<20}  {s.artist[:15]:<15}  [{qs}]")
    return "\n".join(lines)


def _format_album_table(albums: list[AlbumItem]) -> str:
    lines = []
    for a in albums:
        lines.append(f"  {a.id:>10}  {a.album_mid:<16}  {a.title[:25]:<25}  {a.artist or '':<15}")
    return "\n".join(lines)


def _progress_bar(filename: str, current: int, total: int) -> None:
    """在终端打印单行进度条。"""
    if total == 0:
        return
    pct = current * 100 // total
    bar_len = 30
    filled = bar_len * current // total
    bar = "█" * filled + "░" * (bar_len - filled)
    click.echo(f"\r  {filename[:20]:<20} {bar} {pct:>3}%", nl=False)
    if current >= total:
        click.echo()


def _resolve_play_url(client: MusicClient, song: MusicItem, quality: str) -> tuple[str, str]:
    """获取播放 URL，不可用时自动降级到 128k。返回 (url, actual_quality)。"""
    for q in [quality, "128k"] if quality != "128k" else [quality]:
        try:
            return client.get_play_url(song, q), q
        except Exception:
            continue
    raise LXMusicError(f"无可用的音质: {song.title}")


@click.group()
@click.pass_context
def cli(ctx: click.Context) -> None:
    """lxmusic: QQ Music CLI — search, play, and manage playlists."""
    cfg = Config()
    ctx.obj = {
        "client": MusicClient(cfg),
        "config": cfg,
    }


@cli.group()
def search() -> None:
    """搜索音乐 / 专辑。"""
    pass


@search.command("music")
@click.argument("query")
@click.option("--source", default=None, help="音源: tx/wy，默认配置文件或 tx")
@click.option("--page", default=1, type=int)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def search_music_cmd(ctx: click.Context, query: str, source: str | None, page: int, as_json: bool) -> None:
    client: MusicClient = ctx.obj["client"]
    result = client.search_music(query, page, source=source)
    if as_json:
        click.echo(json.dumps(
            {"is_end": result["is_end"], "data": [asdict(s) for s in result["data"]]},
            indent=2, ensure_ascii=False,
        ))
    else:
        if not result["data"]:
            click.echo("无结果")
        else:
            click.echo(_format_music_table(result["data"]))
            click.echo(f"\n第 {page} 页, 共 {len(result['data'])} 条, {'已到末尾' if result['is_end'] else '更多...'}")


@search.command("album")
@click.argument("query")
@click.option("--source", default=None, help="音源: tx/wy，默认配置文件或 tx")
@click.option("--page", default=1, type=int)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def search_album_cmd(ctx: click.Context, query: str, source: str | None, page: int, as_json: bool) -> None:
    client: MusicClient = ctx.obj["client"]
    result = client.search_album(query, page, source=source)
    if as_json:
        click.echo(json.dumps(
            {"is_end": result["is_end"], "data": [asdict(a) for a in result["data"]]},
            indent=2, ensure_ascii=False,
        ))
    else:
        if not result["data"]:
            click.echo("无结果")
        else:
            click.echo(_format_album_table(result["data"]))
            click.echo(f"\n第 {page} 页, 共 {len(result['data'])} 条, {'已到末尾' if result['is_end'] else '更多...'}")


@cli.command("play")
@click.argument("song_ref")
@click.option("--source", default=None, help="音源: tx/wy，默认配置文件或 tx")
@click.option("--quality", default="320k", type=click.Choice(SUPPORTED_QUALITIES))
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def play_cmd(ctx: click.Context, song_ref: str, source: str | None, quality: str, as_json: bool) -> None:
    """获取歌曲播放 URL。"""
    client: MusicClient = ctx.obj["client"]
    song_id, songmid = _resolve_song_id(song_ref)

    song = client.get_music_info(songmid=songmid, song_id=song_id, source=source)
    if not song:
        raise SongNotFoundError(f"未找到歌曲: {song_ref}")

    url, actual_q = _resolve_play_url(client, song, quality)
    if as_json:
        result = {"url": url, "quality": quality, "song": asdict(song)}
        try:
            lyric = client.get_lyric(song.songmid, source=song.source)
            if lyric.get("raw_lrc"):
                result["lyric"] = lyric["raw_lrc"]
        except Exception:
            pass
        click.echo(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        click.echo(url)


@cli.command("download")
@click.argument("song_ref")
@click.option("--source", default=None, help="音源: tx/wy，默认配置文件或 tx")
@click.option("--quality", default="320k", type=click.Choice(SUPPORTED_QUALITIES))
@click.option("--dir", "output_dir", default=".", help="下载目录，默认当前目录")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def download_cmd(ctx: click.Context, song_ref: str, source: str | None, quality: str, output_dir: str, as_json: bool) -> None:
    """下载歌曲到指定目录。"""

    client: MusicClient = ctx.obj["client"]
    song_id, songmid = _resolve_song_id(song_ref)

    song = client.get_music_info(songmid=songmid, song_id=song_id, source=source)
    if not song:
        raise SongNotFoundError(f"未找到歌曲: {song_ref}")

    out = Path(output_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    dest = out / f"{song.id}_{sanitize(song.title)}{QUALITY_EXT.get(quality, '.mp3')}"

    url, actual_q = _resolve_play_url(client, song, quality)
    if song.source == "local":
        import shutil
        shutil.copy2(url, dest)
    else:
        _download_file(url, dest, lambda c, t: _progress_bar(dest.name, c, t))

    if as_json:
        click.echo(json.dumps({"id": song.id, "title": song.title, "path": str(dest), "quality": quality}, indent=2, ensure_ascii=False))
    else:
        click.echo(f"已下载 1 首 → {dest}")
        click.echo(f"  {song.id}  {song.title}  [{quality}]  {dest}")


@cli.command("album")
@click.argument("album_id")
@click.option("--source", default=None, help="音源: tx/wy，默认配置文件或 tx")
@click.option("--quality", default="320k", type=click.Choice(SUPPORTED_QUALITIES))
@click.option("--dir", "output_dir", default=".", help="下载目录")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def album_download_cmd(ctx: click.Context, album_id: str, source: str | None, quality: str, output_dir: str, as_json: bool) -> None:
    """下载专辑所有歌曲到指定目录。"""

    client: MusicClient = ctx.obj["client"]
    out = Path(output_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)

    info = client.get_album_info(album_id, source=source)
    songs = info.get("music_list", [])
    if not songs:
        click.echo("专辑无歌曲或未找到")
        return

    results = []
    for song in songs:
        ext = QUALITY_EXT.get(quality, ".mp3")
        dest = out / f"{song.id}_{sanitize(song.title)}{ext}"
        if dest.exists() and dest.stat().st_size > 0:
            results.append({"id": song.id, "title": song.title, "path": str(dest)})
            continue

        url, actual_q = _resolve_play_url(client, song, quality)
        if Path(url).exists():
            import shutil
            shutil.copy2(url, dest)
        else:
            _download_file(url, dest, lambda c, t: _progress_bar(dest.name, c, t))
        results.append({"id": song.id, "title": song.title, "path": str(dest)})

    if as_json:
        click.echo(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        click.echo(f"专辑 {album_id}: 已下载 {len(results)} 首到 {out}")
        for r in results:
            click.echo(f"  {r['id']}  {r['title']}  ->  {r['path']}")

    # 在下载目录创建同名歌单
    album_name = songs[0].album or album_id
    pl_path = out / f"{sanitize(album_name)}.yaml"
    tracks = []
    for song in songs:
        dest = out / f"{song.id}_{sanitize(song.title)}{QUALITY_EXT.get(quality, '.mp3')}"
        tracks.append({
            "id": song.id,
            "title": song.title,
            "artist": song.artist,
            "path": str(dest),
        })
    with open(pl_path, "w") as f:
        f.write(f"name: {album_name}\ntracks:\n")
        for t in tracks:
            f.write(f"  - {json.dumps(t, ensure_ascii=False)}\n")
    if not as_json:
        click.echo(f"歌单已创建: {pl_path}")


@cli.group()
def playlist() -> None:
    """歌单管理。"""
    pass


@playlist.command("create")
@click.argument("name")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def playlist_create_cmd(ctx: click.Context, name: str, as_json: bool) -> None:
    """创建空歌单。"""
    cfg: Config = ctx.obj["config"]
    store = PlaylistStore(cfg.playlist_dir)
    try:
        path = store.create(name)
        if as_json:
            click.echo(json.dumps({"ok": True, "path": str(path)}, indent=2, ensure_ascii=False))
        else:
            click.echo(f"歌单已创建: {path}")
    except FileExistsError as e:
        click.echo(f"错误: {e}", err=True)
        if not as_json:
            raise click.Abort()


@playlist.command("add")
@click.argument("name")
@click.argument("query")
@click.option("--source", default=None, help="音源: tx/wy，默认配置文件或 tx")
@click.option("--quality", default="320k", type=click.Choice(SUPPORTED_QUALITIES))
@click.option("--limit", default=20, type=int, help="拉取搜索结果条数（自动翻页，默认 20）")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def playlist_add_cmd(ctx: click.Context, name: str, query: str, source: str | None, quality: str, limit: int, as_json: bool) -> None:
    """搜索歌曲并添加到歌单。"""
    client: MusicClient = ctx.obj["client"]
    cfg: Config = ctx.obj["config"]

    # 自动翻页拉取 limit 条
    songs: list[MusicItem] = []
    page = 1
    while len(songs) < limit:
        result = client.search_music(query, page=page, source=source)
        data = result.get("data", [])
        if not data:
            break
        songs.extend(data)
        if result.get("is_end"):
            break
        page += 1
    songs = songs[:limit]

    if not songs:
        click.echo("无搜索结果", err=True)
        raise click.Abort()

    click.echo(f"搜索结果：\n{_format_music_table(songs)}")
    choice = click.prompt(f"选择序号 (逗号分隔多选，空=全部)", default="all", show_default=False)

    if not choice.strip() or choice.strip().lower() == "all":
        indices = list(range(len(songs)))
    else:
        indices = []
        for part in choice.split(","):
            part = part.strip()
            if part:
                try:
                    idx = int(part) - 1
                    if 0 <= idx < len(songs):
                        indices.append(idx)
                except ValueError:
                    pass
        if not indices:
            click.echo("无效选择", err=True)
            raise click.Abort()

    store = PlaylistStore(cfg.playlist_dir)
    cache_dir = cfg.cache_dir
    added = []

    for idx in indices:
        song = songs[idx]
        used_quality = quality
        dest = cache_dir / f"{song.id}_{sanitize(song.title)}{QUALITY_EXT.get(quality, '.mp3')}"

        if not dest.exists() or dest.stat().st_size == 0:
            try:
                url, used_quality = _resolve_play_url(client, song, used_quality)
            except LXMusicError:
                click.echo(f"  跳过 {song.title}: 无可用音质")
                continue
            dest = cache_dir / f"{song.id}_{sanitize(song.title)}{QUALITY_EXT.get(used_quality, '.mp3')}"
            if Path(url).exists():
                import shutil
                shutil.copy2(url, dest)
            else:
                _download_file(url, dest, lambda c, t: _progress_bar(dest.name, c, t))

        track = {
            "id": song.id,
            "title": song.title,
            "artist": song.artist,
            "path": str(dest),
        }
        store.add(name, track)
        added.append(track)

    if as_json:
        click.echo(json.dumps({"ok": True, "name": name, "tracks": added}, indent=2, ensure_ascii=False))
    else:
        click.echo(f"已添加到歌单「{name}」: {len(added)} 首")
        for t in added:
            click.echo(f"  {t['title']} - {t['artist']}")


@playlist.command("show")
@click.argument("name")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def playlist_show_cmd(ctx: click.Context, name: str, as_json: bool) -> None:
    """显示歌单曲目。"""
    cfg: Config = ctx.obj["config"]
    store = PlaylistStore(cfg.playlist_dir)
    data = store.get(name)
    tracks = data.get("tracks", [])

    if as_json:
        click.echo(json.dumps({"name": name, "tracks": tracks}, indent=2, ensure_ascii=False))
    else:
        if not tracks:
            click.echo("歌单为空")
        else:
            click.echo(f"歌单: {name} ({len(tracks)} 首)\n")
            for idx, t in enumerate(tracks, 1):
                click.echo(f"  {idx:>3}.  {t['title']:<20}  {t.get('artist', ''):<15}  {t['path']}")


@playlist.command("play")
@click.argument("name")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def playlist_play_cmd(ctx: click.Context, name: str, as_json: bool) -> None:
    """输出歌单所有歌曲的可播放信息（编号列表）。"""
    cfg: Config = ctx.obj["config"]
    store = PlaylistStore(cfg.playlist_dir)
    data = store.get(name)
    tracks = data.get("tracks", [])

    if not tracks:
        click.echo("歌单为空")
        return

    if as_json:
        click.echo(json.dumps({"name": name, "tracks": tracks}, indent=2, ensure_ascii=False))
    else:
        click.echo(f"歌单: {name} ({len(tracks)} 首)\n")
        # 输出编号列表，与 show 一致
        for idx, t in enumerate(tracks, 1):
            click.echo(f"  {idx:>3}.  {t['title']:<20}  {t.get('artist', ''):<15}  {t['path']}")


@playlist.command("export")
@click.argument("name")
@click.option("--dir", "output_dir", default=".", help="导出目录，默认当前目录")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def playlist_export_cmd(ctx: click.Context, name: str, output_dir: str, as_json: bool) -> None:
    """导出歌单为 M3U8 格式。"""
    cfg: Config = ctx.obj["config"]
    store = PlaylistStore(cfg.playlist_dir)
    out = Path(output_dir).expanduser().resolve()
    dest = store.export_m3u(name, out / f"{name}.m3u")
    if as_json:
        click.echo(json.dumps({"path": str(dest), "name": name}, indent=2, ensure_ascii=False))
    else:
        click.echo(f"M3U 已导出: {dest}")


@cli.group()
def config() -> None:
    """配置管理。"""
    pass


@config.command("set")
@click.argument("key")
@click.argument("value", required=False, default="")
@click.pass_context
def config_set_cmd(ctx: click.Context, key: str, value: str) -> None:
    """设置配置项。value 为空时删除该项。

    常用 key: api_key, api_url, default_source, default_quality, data_dir, music_dir
    """
    cfg: Config = ctx.obj["config"]
    cfg.set(key, value)
    click.echo(f"已设置 {key}={value or '<删除>'}")


@config.command("show")
@click.pass_context
def config_show_cmd(ctx: click.Context) -> None:
    """显示当前配置。"""
    cfg: Config = ctx.obj["config"]
    click.echo(yaml.dump(cfg._data, default_flow_style=False, allow_unicode=True).strip())
