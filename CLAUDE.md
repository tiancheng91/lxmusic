# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 常用命令

```bash
# 安装依赖
uv sync

# 运行测试
uv run pytest tests/ -v

# 运行单个测试
uv run pytest tests/test_tx_music.py::TestPlaylistStore::test_create_and_get -v

# 构建
uv build

# 本地安装（开发模式）
uv tool install .

# 运行 CLI
uv run lxmusic --help
uv run lxmusic search music "周杰伦"
uv run lxmusic mcp                          # 标准 MCP server
uv run lxmusic xiaozhi                      # xiaozhi 兼容 MCP server (stdio)
uv run lxmusic xiaozhi --wss <url>          # 通过 WSS 注册到小智
```

## 架构

`lxmusic/` 包采用三层组合架构：

### 1. Source 层（搜索与元信息）

`lxmusic/sources/__init__.py` 定义 `Source(ABC)` 抽象基类，要求实现：
`search_music` / `search_album` / `get_music_info` / `get_album_info` / `get_lyric` / `get_audio_headers` / `close`。

三个实现：
- `tx.py` — QQ 音乐（通过 `musicu.fcg` 接口）
- `wy.py` — 网易云音乐
- `local.py` — 本地音乐文件 + 歌单 YAML 扫描

`LocalSource` 特殊性：
- 扫描 `cfg.local_dirs`（由 `music_dir` 拆分而来，逗号分隔多目录）
- 同时扫描 `*.yaml` 文件，解析 `{name, tracks}` 结构为歌单
- `search_album` 按 YAML 中 `name` 字段匹配歌单名
- `get_album_info` 按 `album_mid`（歌单名）查找对应 YAML 返回曲目
- 文件 ID 使用 MD5 哈希（确定性，跨进程稳定），不能用 `hash()`（有随机种子）
- `get_music_info` 支持 `songmid`（文件路径）和 `song_id`（哈希）两种查找

### 2. PlayURLProvider 层（播放直链）

`lxmusic/playurl.py` 定义 `PlayURLProvider(ABC)`，实现 `ShiqianjiangProvider`：
- 调用 `https://source.shiqianjiang.cn/api/music/url`
- 需要 API 密钥（从 `cfg.api_key` 获取）

### 3. MusicClient 组合层

`lxmusic/client.py` 中 `MusicClient` 组合 Source + PlayURLProvider：
- `_get_source(name)` 懒加载并缓存 Source 实例（`LocalSource` 接收 `cfg.local_dirs`）
- `get_play_url(song, quality)` 对本地源直接返回 `song.songmid`（即文件路径），远程源走 PlayURLProvider
- 通过 `source` 参数覆盖默认音源

## CLI 与 MCP

### 入口分发

`lxmusic/main.py` 根据 `sys.argv[1]` 分发：
- `mcp` → 标准 MCP server（FastMCP，stdio）
- `xiaozhi` → xiaozhi 兼容 MCP server（低层 `mcp.server.Server`）
- 其他 → CLI 命令组（click）

### CLI 命令组（`cli.py`）

`search` / `play` / `download` / `album` / `playlist` / `config` / `xiaozhi`

关键实现细节：
- `_resolve_play_url(client, song, quality)` — 请求音质不可用时自动降级到 128k
- `playlist add` 支持 `--limit`（默认 20）自动翻页拉取搜索结果
- `album` 下载时若 URL 是本地路径用 `shutil.copy2`，否则走 `_download_file`
- 下载进度条通过 `_progress_bar` 回调显示

### xiaozhi MCP（`mcp_xiaozhi.py`）

实现小智智能体协议：
- `musicPlayer(query)` → 返回 `EmbeddedResource` 列表
- `resource/read` → 惰性解析播放地址 + LRU 缓存（5 分钟 TTL）
- 搜索策略：本地源优先 `search_album`（匹配歌单）再 `search_music`；远程源只 `search_music`
- `_PlayURLCache` 自己实现 LRU + TTL（不用 `functools.lru_cache`，因为要按 key 查找）
- WSS 模式通过子进程启动 stdio MCP，双向管道转发
- 启动时输出 `logging` 日志到 stderr，包含音源/音质/密钥状态

## 配置系统

`lxmusic/config.py` 采用两层优先级：**环境变量 > config.yaml > 默认值**

用户只需配置两个路径：
- `data_dir` — lxmusic 数据目录（默认 `~/.config/lxmusic`）
- `music_dir` — 本地音乐文件目录（支持逗号分隔多目录）

子路径通过 `@property` 自动推导：
- `playlist_dir` → `data_dir/playlists/`
- `cache_dir` → `data_dir/cache/`
- `local_dirs` → `music_dir` 按逗号拆分成的列表

`Config.set(key, value)` 写入 YAML 文件并刷新内存；空值删除该项。

`~/.config/lxmusic/config.yaml` 首次运行由 `Config.save_defaults()` 生成。

## 数据模型

`lxmusic/models.py`：
- `MusicItem` — id, songmid, title, artist, album, albummid, artwork, qualities, source
- `AlbumItem` — id, album_mid, title, artist, artwork, date, singer_mid, source

`source` 字段决定后续路由（`local` 走文件路径，`tx`/`wy` 走 PlayURLProvider）。

## 异常

`lxmusic/errors.py`：
- `LXMusicError` 基类，带 `exit_code` 用于 CLI 退出码
- `QualityNotAvailableError` / `SongNotFoundError` / `PlaylistNotFoundError` 等

## 存储与歌单

`lxmusic/storage.py`：
- `_download_file(url, dest, progress_cb)` — 流式下载，`.tmp` 后缀原子重命名
- `PlaylistStore` — YAML 歌单管理（create / get / add / list_all / export_m3u）
- 歌单格式：`name:` 顶层字段，`tracks:` 为单行 JSON 列表
- 加载时 `tracks: null` 会被归一化为 `[]`

## 发布流程

每次 release 前必须：

1. 更新 `pyproject.toml` 中的 `version` 字段为待发布版本
2. 提交版本号变更：`git commit -m "chore: bump version to x.y.z"`
3. 创建并推送 tag：`git tag vx.y.z && git push origin vx.y.z`
4. 通过 `gh release create vx.y.z` 创建 GitHub Release

Tag 必须指向包含版本号更新的 commit，否则 PyPI 发布的版本号会不匹配。

GitHub Actions：
- `.github/workflows/ci.yml` — push/PR 触发，运行 pytest + uv build
- `.github/workflows/publish.yml` — tag `v*` 触发，发布到 PyPI（trusted publishing）

## 测试

`tests/test_tx_music.py` 包含：
- `TestParseQualities` — QQ 音乐音质解析
- `TestFormatMusicItem` — 元信息格式化
- `TestPlaylistStore` — YAML 歌单增删查导出

CI 中 `uv sync` + `uv pip install pytest` 安装测试依赖（pytest 不在主依赖中）。
