lxmusic — QQ音乐 & 网易云 CLI + MCP 工具

多音源：QQ音乐（tx）、网易云（wy）、本地文件/歌单（local）。
播放默认返回播放 URL 或本地路径；--json 输出含歌词。

需要 API 密钥，从 https://source.shiqianjiang.cn/ 获取，通过 `lxmusic config set api_key xxx` 配置。

## CLI

### 搜索

lxmusic search music <query> [--source tx|wy|local] [--page 1] [--json]
lxmusic search album <query> [--source tx|wy|local] [--json]

- 远程源搜索歌曲；本地源搜索音频文件 + 歌单 YAML
- 本地源 search album 按 YAML 文件中 name 字段匹配

### 播放

lxmusic play <song_id> [--quality 128k|320k|flac|hires] [--json]
lxmusic play <song_id> --json

- 不支持的音质自动降级到 128k
- --json 输出含歌词（远程源）

### 下载

lxmusic download <song_id> [--dir .] [--source tx|wy] [--quality 320k]
lxmusic album <album_id> [--dir .] [--source tx|wy|local] [--quality 320k]

- album 支持本地歌单名：lxmusic album "巧虎儿歌" --source local
- 带进度条，不可用音质自动降级

### 歌单

lxmusic playlist create <name>              # 创建空歌单
lxmusic playlist add <name> <query>         # 搜索 → 交互选择 → 下载 → 添加
lxmusic playlist show <name>
lxmusic playlist play <name>
lxmusic playlist export <name> [--dir .]    # 导出 M3U8

- add 支持多选（回车=全部，逗号分隔=多选）
- 歌单存储在 data_dir/playlists/ 下为 YAML 格式

### 配置

lxmusic config set <key> <value>
lxmusic config show

常用 key: api_key, default_source, default_quality, data_dir, music_dir

## MCP Tools (lxmusic mcp)

- search_music(query, page, source)
- search_album(query, page, source)
- play_music(song_id, songmid, quality, source)

## xiaozhi MCP (lxmusic xiaozhi)

- musicPlayer(query) → ResourceLink 列表（含搜索策略）
- resource/read → base64 音频数据

搜索策略：
- 本地源：先 search album 匹配歌单 → 再 search music 匹配文件
- 远程源：只 search music

协议参考: https://github.com/hackers365/mcp_audio_server

## 配置

优先级：环境变量 > config.yaml > 默认值
配置文件：~/.config/lxmusic/config.yaml

用户只需关心两个配置：
- data_dir: lxmusic 数据目录（playlists/ cache/ library/）
- music_dir: 本地音乐文件目录

默认音源：tx（可改为 local 或 wy）
默认音质：320k（xiaozhi 使用 128k）