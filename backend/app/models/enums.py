import enum


class SourceType(str, enum.Enum):
    VIDEO = "video"
    PLAYLIST = "playlist"
    CHANNEL = "channel"


class EntryAvailability(str, enum.Enum):
    AVAILABLE = "available"
    NEEDS_AUTH = "needs_auth"
    GEO_BLOCKED = "geo_blocked"
    PRIVATE = "private"
    REMOVED = "removed"
    UNKNOWN = "unknown"


class JobKind(str, enum.Enum):
    DOWNLOAD = "download"
    COMPILE = "compile"
    RESCAN = "rescan"


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StageType(str, enum.Enum):
    REVALIDATE_FORMATS = "revalidate_formats"
    DOWNLOAD_VIDEO = "download_video"
    DOWNLOAD_AUDIO = "download_audio"
    MERGE = "merge"
    SPONSORBLOCK = "sponsorblock"
    EMBED_SUBTITLES = "embed_subtitles"
    NORMALIZE_AUDIO = "normalize_audio"
    FINALIZE = "finalize"


class StageStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ArtifactKind(str, enum.Enum):
    VIDEO_STREAM = "video_stream"
    AUDIO_STREAM = "audio_stream"
    MERGED = "merged"
    CLEANED = "cleaned"
    SUBTITLED = "subtitled"
    NORMALIZED = "normalized"


class SponsorBlockAction(str, enum.Enum):
    KEEP = "keep"
    MARK_CHAPTERS = "mark_chapters"
    REMOVE = "remove"


class ConcurrencyMode(str, enum.Enum):
    SAFE = "safe"
    BALANCED = "balanced"
    POWER = "power"


class SubscriptionFilterType(str, enum.Enum):
    IGNORE_SHORTS = "ignore_shorts"
    MIN_DURATION = "min_duration"
    MAX_DURATION = "max_duration"
    KEYWORD_INCLUDE = "keyword_include"
    KEYWORD_EXCLUDE = "keyword_exclude"
    IGNORE_LIVE = "ignore_live"
