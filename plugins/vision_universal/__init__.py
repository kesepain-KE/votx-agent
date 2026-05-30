# -*- coding: utf-8 -*-
"""Vision Universal Skill Package"""

from .tool import vision_analyze, SCHEMA_VISION_ANALYZE, register

# 兼容旧引用
analyze_image = vision_analyze
SCHEMA = SCHEMA_VISION_ANALYZE

__all__ = ['vision_analyze', 'analyze_image', 'SCHEMA', 'SCHEMA_VISION_ANALYZE', 'register']
