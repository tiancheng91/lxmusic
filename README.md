<div align="center">
  <h1>lxmusic</h1>
  <p>QQ音乐 / 网易云 CLI & MCP 工具 — 搜索、播放、下载、歌单管理</p>
  <p>
    <a href="#quick-start">Quick Start</a> •
    <a href="#cli-usage">CLI</a> •
    <a href="#mcp-server">MCP</a> •
    <a href="#configuration">Configuration</a> •
    <a href="#build--publish">Build</a>
  </p>
</div>

---

## Features

- **搜索** — 音乐 / 专辑，支持 QQ音乐（tx）和 网易云（wy）双音源
- **播放** — 获取播放直链，`--json` 含歌词
- **下载** — 单曲 / 整张专辑，带进度条，文件名 `ID_歌名.mp3`
- **歌单** — 创建、搜索添加、查看、播放、导出 M3U8
- **配置** — `lxmusic config set` 运行时修改配置
- **MCP** — 标准 MCP server（搜索/播放/歌单工具）
- **xiaozhi 兼容** — 支持小智智能体协议，搜索并播放音乐（工具本身不提供音乐内容）
- **多音质** — 128k / 320k / FLAC / Hi-Res

## Quick Start

```bash
# 安装
uv tool install lxmusic
# 或: pipx install lxmusic

# 设置 API 密钥（从 https://source.shiqianjiang.cn/ 获取）
lxmusic config set api_key your_key_here

# 搜索音乐（QQ音乐）
lxmusic search music "周杰伦"

# 搜索音乐（网易云）
lxmusic search music "周杰伦" --source wy

# 播放，返回 URL 和歌词
lxmusic play 102065756 --json

# 下载单曲
lxmusic download 102065756 --dir ~/Music

# 下载整张专辑
lxmusic album 003DFRzD192KKD --dir ~/Music/七里香

# 启动 MCP server
lxmusic mcp
```

## Installation

### 从 PyPI

```bash
uv tool install lxmusic
# 或: pipx install lxmusic
```

### 从源码

```bash
git clone <repo-url>
cd lxmusic
uv sync
```

### 配置默认音源

```yaml
# ~/.config/lxmusic/config.yaml
default_source: wy
```

## CLI Usage

### Search

```bash
lxmusic search music "儿歌" --page 1
lxmusic search album "范特西"
lxmusic search music "周杰伦" --source wy --json
```

### Play

```bash
lxmusic play 102065756
lxmusic play 102065756 --quality flac
lxmusic play 102065756 --json
```

```json
{
  "url": "http://...mp3",
  "quality": "320k",
  "lyric": "[ti:七里香]\n...",
  "song": { "id": 102065756, "title": "七里香", "artist": "周杰伦", ... }
}
```

### Download

```bash
lxmusic download 102065756                          # 当前目录
lxmusic download 102065756 --dir ~/Music             # 指定目录
lxmusic download 509781655 --source wy --dir ~/Music # 网易云歌曲
```

### Album

```bash
lxmusic album 003DFRzD192KKD                          # 下载整张专辑
lxmusic album 003DFRzD192KKD --dir ~/Music/七里香       # 指定目录
lxmusic album 003DFRzD192KKD --quality flac             # 无损音质
lxmusic album 003DFRzD192KKD --json                     # JSON 输出
```

### Playlist

```bash
lxmusic playlist create "我的最爱"
lxmusic playlist add "我的最爱" "周杰伦 七里香"          # 搜索 → 交互选择 → 下载 → 添加
lxmusic playlist add "我的最爱" "周杰伦 晴天"             # 回车=全部，逗号分隔多选
lxmusic playlist show "我的最爱"
lxmusic playlist play "我的最爱"
lxmusic playlist export "我的最爱" --dir ~/Music          # 导出 M3U8
```

### Config

```bash
lxmusic config set api_key your_key_here
lxmusic config set default_source wy
lxmusic config set default_quality flac
lxmusic config set api_key ""                             # 删除配置项
lxmusic config show                                       # 查看当前配置
```

## MCP Server

### 标准 MCP

```bash
lxmusic mcp
```

标准工具：搜索、播放、歌单（详情见 skills/lxmusic.md）

### xiaozhi 兼容 MCP

**免责声明：** lxmusic 工具本身不提供任何音乐内容。它仅作为搜索和播放的中介层，通过第三方 API 获取音乐元信息和播放链接，这些链接指向用户自行部署的第三方服务。用户需自行确保使用方式符合相关法律法规。

lxmusic 实现了 xiaozhi 智能体协议（[协议参考](https://github.com/hackers365/mcp_audio_server)），支持通过 `musicPlayer` 工具搜索并播放音乐。

#### 协议流程

1. `musicPlayer(query)` → 搜索音乐，返回 `resource://read_<source>_<id>` 列表
2. `resource/read` → 客户端请求资源时，惰性解析播放地址并从 CDN 拉取音频数据（base64 编码），结果 LRU 缓存 5 分钟

#### 配置示例

```json
{
  "mcpServers": {
    "lxmusic-xiaozhi": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/lxmusic", "lxmusic", "xiaozhi"]
    }
  }
}
```

#### 启动方式

```bash
# stdio 模式（默认，适用于 Claude Code 等 MCP 客户端）
lxmusic xiaozhi

# WebSocket 模式（注册到小智云端）
lxmusic xiaozhi --wss "wss://api.xiaozhi.me/mcp/?token=your_token"
```

#### 使用本地音乐源

配置本地音乐目录后，lxmusic 会扫描目录中的音频文件并通过 `musicPlayer` 返回：

```bash
# 设置本地音乐目录
lxmusic config set local_dirs /path/to/your/music

# 搜索本地音乐（source 为 local）
lxmusic search music "周杰伦" --source local

# xiaozhi 模式下搜索本地音乐
# musicPlayer("周杰伦") 会自动包含本地目录中的匹配文件
```

本地音乐播放时，`resource/read` 直接从本地文件读取，无需网络传输。

#### 网络音源

```bash
# 设置 API 密钥（从 https://source.shiqianjiang.cn/ 获取）
lxmusic config set api_key your_key_here

# xiaozhi 默认使用 128k 低码率播放，减少网络开销
# 搜索时自动包含 QQ音乐 和 网易云 结果
lxmusic xiaozhi
```

## Configuration

优先级：**环境变量 > config.yaml > 默认值**

| Environment Variable | Description | Default |
|---|---|---|
| `LX_MUSIC_API_KEY` | API 密钥（必填） | — |
| `LX_MUSIC_API_URL` | 后端 API 地址 | `https://source.shiqianjiang.cn/api/music` |
| `LX_MUSIC_DEFAULT_SOURCE` | 默认音源 | `tx` |
| `LX_MUSIC_DEFAULT_QUALITY` | 默认音质 | `320k` |
| `LX_MUSIC_LOCAL_DIRS` | 本地音乐目录（逗号分隔多目录） | `~/.config/lxmusic/library` |
| `LX_MUSIC_LIBRARY_DIR` | 曲库索引目录 | `~/.config/lxmusic/library` |
| `LX_MUSIC_PLAYLIST_DIR` | 歌单目录 | `~/.config/lxmusic/playlists` |
| `LX_MUSIC_CACHE_DIR` | 下载缓存目录 | `~/.config/lxmusic/cache` |

`~/.config/lxmusic/config.yaml`（首次运行自动生成），可通过 `lxmusic config set` 管理：

```yaml
api_key: your_key_here
default_source: wy
```

所有数据集中存储在 `~/.config/lxmusic/` 下：

- `library/` — 曲库元信息（scan.json, index.db）
- `playlists/` — YAML 歌单文件
- `cache/` — 下载缓存

`lxmusic playlist add` 下载的歌曲缓存到 `cache_dir`（默认 `~/.config/lxmusic/cache/`），`lxmusic download` 默认下载到当前目录。

## Project Structure

```
lxmusic/
├── lxmusic/
│   ├── sources/
│   │   ├── __init__.py    # Source 抽象基类
│   │   ├── tx.py          # QQ 音乐源
│   │   └── wy.py          # 网易云音乐源
│   ├── client.py          # MusicClient 组合层
│   ├── playurl.py         # 播放提供器（shiqianjiang）
│   ├── config.py          # 配置加载
│   ├── errors.py          # 异常类
│   ├── models.py          # 数据模型
│   ├── storage.py         # 缓存 + 歌单
│   ├── cli.py             # CLI 命令（play/download/album/playlist/search）
│   ├── mcp_server.py      # 标准 MCP server
│   ├── mcp_xiaozhi.py     # xiaozhi 兼容 MCP server
│   └── main.py            # 入口
├── tests/
├── scripts/
├── skills/
├── .github/workflows/
│   ├── ci.yml
│   └── publish.yml
├── pyproject.toml
└── README.md
```

## Build & Publish

```bash
uv build
uv publish
```

## License

MIT
