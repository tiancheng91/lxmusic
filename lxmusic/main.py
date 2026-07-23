"""入口：CLI 或 MCP 模式。"""

import sys

from lxmusic.config import Config
from lxmusic.client import MusicClient
from lxmusic.errors import LXMusicError
from lxmusic.mcp_server import create_mcp_server


def main() -> None:
    cfg = Config()
    cfg.save_defaults()

    if len(sys.argv) > 1 and sys.argv[1] == "mcp":
        client = MusicClient(cfg)
        server = create_mcp_server(cfg, client)
        server.run()
    else:
        from lxmusic.cli import cli
        try:
            cli()
        except LXMusicError as e:
            import click
            click.echo(f"错误: {e}", err=True)
            sys.exit(e.exit_code)


if __name__ == "__main__":
    main()
