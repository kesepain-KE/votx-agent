# -*- coding: utf-8 -*-
"""Video Generation Skill Package"""

from .tool import SCHEMA_DOWNLOAD, SCHEMA_GENERATE, SCHEMA_STATUS, register, video_download, video_generate, video_status

__all__ = [
    "video_generate",
    "video_status",
    "video_download",
    "SCHEMA_GENERATE",
    "SCHEMA_STATUS",
    "SCHEMA_DOWNLOAD",
    "register",
]
