<div align="center">
  <h1>lxmusic</h1>
  <p>QQ音乐 / 网易云 CLI & MCP 工具 — 搜索、播放、下载、歌单管理</p>
  <p>
    <a href="#quick-start">Quick Start</a> •
    <a href="#cli-usage">CLI</a> •
    <a href="#mcp-server">MCP</a> •
    <a href="#configuration">Configuration</a> •
    <a href="#local-source">Local Source</a> •
    <a href="#build--publish">Build</a>
  </p>
</div>

---

## Features

- **多音源** — QQ音乐（tx）、网易云（wy）、本地文件扫描（local）
- **搜索** — 音乐 / 专辑，音源间自由切换
- **播放** — 获取播放直链或本地路径，`--json` 含歌词
- **下载** — 单曲 / 整张专辑下载，带进度条，自动降级音质
- **歌单** — YAML 存储，创建、搜索添加（多选）、查看、播放、导出 M3U8
- **本地源** — 扫描音乐目录，同时解析 YAML 歌单文件，`search album` 按歌单名匹配
- **配置** — `lxmusic config set` 运行时修改，只需关心 `data_dir` + `music_dir`
- **MCP** — 标准 MCP server + xiaozhi 兼容 MCP（WSS 注册）
- **多音质** — 128k / 320k / FLAC / Hi-Res，不可用时自动降级

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

# 搜索专辑
lxmusic search album "范特西"

# 播放，返回 URL 和歌词
lxmusic play 102065756 --json

# 下载单曲
lxmusic download 102065756 --dir ~/Music

# 下载整张专辑（先搜索得到 album_id，再下载）
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

## CLI Usage

### Search

```bash
lxmusic search music "儿歌" --page 1
lxmusic search album "范特西"
lxmusic search music "周杰伦" --source wy --json
lxmusic search album "我的最爱" --source local      # 本地歌单匹配
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
lxmusic album 003DFRzD192KKD                          # 远程专辑
lxmusic album "巧虎儿歌" --source local                 # 本地歌单曲目
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
lxmusic config set api_key your_key_here                 # 设置密钥
lxmusic config set default_source local                  # 默认本地源
lxmusic config set music_dir ~/Music                     # 音乐文件目录
lxmusic config set data_dir ~/.config/lxmusic             # 数据目录
lxmusic config set default_quality flac                   # 默认音质
lxmusic config set api_key ""                             # 删除配置项
lxmusic config show                                       # 查看当前配置
```

## MCP Server

### 标准 MCP

```bash
lxmusic mcp
```

标准工具：search_music, search_album, play_music

### xiaozhi 兼容 MCP

**免责声明：** lxmusic 工具本身不提供任何音乐内容。它仅作为搜索和播放的中介层，通过第三方 API 获取音乐元信息和播放链接，这些链接指向用户自行部署的第三方服务。用户需自行确保使用方式符合相关法律法规。

lxmusic 实现了 xiaozhi 智能体协议（[协议参考](https://github.com/hackers365/mcp_audio_server)），支持通过 `musicPlayer` 工具搜索并播放音乐。

#### 协议流程

1. `musicPlayer(query)` → 搜索音乐，返回 `resource://read_<source>_<id>` 列表
2. `resource/read` → 客户端请求资源时，惰性解析播放地址（LRU 缓存 5 分钟），本地文件直接读取，远程 CDN 拉取后 base64 返回

#### 搜索策略

- **本地源（default_source=local）**：优先搜索 `search album` 匹配歌单名返回整张歌单，再搜索 `search music` 按文件名匹配
- **远程源（tx/wy）**：只搜索 `search music` 返回歌曲

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

```bash
# 设置本地音乐目录
lxmusic config set music_dir /path/to/your/music
lxmusic config set default_source local

# 搜索本地音乐 — album 优先匹配歌单，music 按文件名匹配
lxmusic search album "巧虎" --source local
lxmusic search music "小毛驴" --source local

# 下载本地歌单所有歌曲
lxmusic album "巧虎儿歌" --source local --dir ./巧虎儿歌
```

本地音乐播放时 `resource/read` 直接从本地文件读取，无需网络传输。

#### 网络音源

```bash
# 设置 API 密钥（从 https://source.shiqianjiang.cn/ 获取）
lxmusic config set api_key your_key_here

# xiaozhi 默认使用 128k 低码率播放，减少网络开销
lxmusic xiaozhi
```

## Local Source

本地源支持两种资产：

- **音频文件** — `.mp3` `.flac` `.wav` `.m4a` `.ogg` `.wma`，按文件名搜索
- **歌单 YAML** — 目录下 `*.yaml` 文件，解析 `name` + `tracks` 结构，通过 `search album` 匹配歌单名

YAML 格式示例（`巧虎儿歌.yaml`）：

```yaml
name: 巧虎儿歌
tracks:
  - {"id": 1, "title": "小毛驴", "artist": "儿童歌曲", "path": "/music/小毛驴.mp3"}
  - {"id": 2, "title": "粉刷匠", "artist": "儿童歌曲", "path": "/music/粉刷匠.mp3"}
```

## Configuration

### 配置项说明

优先级：**环境变量 > config.yaml > 默认值**

| Environment Variable | Description | Default |
|---|---|---|
| `LX_MUSIC_API_KEY` | API 密钥（必填） | — |
| `LX_MUSIC_API_URL` | 后端 API 地址 | `https://source.shiqianjiang.cn/api/music` |
| `LX_MUSIC_DEFAULT_SOURCE` | 默认音源（tx/wy/local） | `tx` |
| `LX_MUSIC_DEFAULT_QUALITY` | 默认音质（128k/320k/flac/hires） | `320k` |
| `LX_MUSIC_DATA_DIR` | lxmusic 数据目录 | `~/.config/lxmusic` |
| `LX_MUSIC_MUSIC_DIR` | 本地音乐目录（逗号分隔多目录） | `~/.config/lxmusic/library` |

### 目录结构

用户只需要关心两个路径：**数据放哪** 和 **音乐文件在哪**，其余子目录自动推导：

```
data_dir/                    # lxmusic 数据目录（默认 ~/.config/lxmusic）
├── config.yaml              # 配置文件
├── playlists/               # 歌单 YAML 文件
├── cache/                   # 下载缓存（playlist add 下载的音频）
├── library/                 # 曲库索引
└── history/                 # 播放历史

music_dir/                   # 用户音乐文件目录（可多个，逗号分隔）
└── 巧虎儿歌/
    ├── *.mp3
    └── 巧虎儿歌.yaml        # 歌单文件（自动识别）
```

### 配置示例

```yaml
# ~/.config/lxmusic/config.yaml
api_key: your_key_here
api_url: https://source.shiqianjiang.cn/api/music
default_source: local          # 默认使用本地源
default_quality: 320k
data_dir: ~/.config/lxmusic     # 数据目录
music_dir: ~/Music,/mnt/music  # 本地音乐目录（多个用逗号分隔）
```

### 常用命令

```bash
# 查看当前配置
lxmusic config show

# 设置 API 密钥
lxmusic config set api_key your_key_here

# 切换默认音源
lxmusic config set default_source local

# 设置本地音乐目录（支持多个）
lxmusic config set music_dir "~/Music,/mnt/music"

# 改变数据目录
lxmusic config set data_dir ~/.config/lxmusic

# 删除配置项（恢复默认）
lxmusic config set api_key ""
```

### 路径说明

- `playlist_dir` → `data_dir/playlists/` — `lxmusic playlist` 命令操作的文件
- `cache_dir` → `data_dir/cache/` — `lxmusic playlist add` 下载的音频缓存
- `local_dirs` → `music_dir` 的值 — `LocalSource` 扫描的目录
- `lxmusic download` 默认下载到**当前目录**，`--dir` 指定其他位置

## Build & Publish

```bash
uv build
uv publish
```

## License

MIT