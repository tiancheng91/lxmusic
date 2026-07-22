"""自定义异常。"""


class LXMusicError(Exception):
    """Base error."""
    exit_code = 1


class ApiKeyInvalidError(LXMusicError):
    exit_code = 2


class RateLimitedError(LXMusicError):
    exit_code = 3


class SongNotFoundError(LXMusicError):
    exit_code = 4


class NetworkError(LXMusicError):
    exit_code = 5


class PlaylistNotFoundError(LXMusicError):
    exit_code = 6


class SongAlreadyInPlaylistError(LXMusicError):
    exit_code = 7


class QualityNotAvailableError(LXMusicError):
    exit_code = 8
