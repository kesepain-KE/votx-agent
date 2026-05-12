"""system prompt 缓存 — 按源文件 mtime 做缓存失效"""
import os
from pathlib import Path


_cache: dict[str, tuple[str, int]] = {}  # key -> (prompt, hash)


def _mtime(path: str | Path) -> int:
    """返回文件 mtime 纳秒，不存在返回 -1"""
    try:
        return os.stat(str(path)).st_mtime_ns
    except OSError:
        return -1


def _dir_max_mtime(directory: str | Path, pattern: str = "*") -> int:
    """返回目录下匹配文件的最大 mtime，不存在返回 -1"""
    p = Path(directory)
    if not p.is_dir():
        return -1
    mtimes = []
    for f in p.glob(pattern):
        try:
            mtimes.append(f.stat().st_mtime_ns)
        except OSError:
            pass
    return max(mtimes) if mtimes else -1


def _compute_cache_key(root: str, user_dir: str) -> int:
    """根据所有源文件的 mtime 计算缓存 key（hash）"""
    mtimes = []

    # self_soul.md
    mtimes.append(_mtime(os.path.join(user_dir, "self_soul.md")))
    # config/soul.md
    mtimes.append(_mtime(os.path.join(root, "config", "soul.md")))
    # AGENTS.md
    mtimes.append(_mtime(os.path.join(root, "AGENTS.md")))
    # skills 目录下所有 SKILL.md、tool.py、_meta.json
    skills_dir = os.path.join(root, "skills")
    for f in Path(skills_dir).rglob("*"):
        if f.name in ("SKILL.md", "tool.py", "_meta.json"):
            mtimes.append(_mtime(str(f)))
    # improve/permanent (memory + self-improving + ontology)
    mtimes.append(_dir_max_mtime(os.path.join(user_dir, "improve", "memory", "permanent"), "*.md"))
    mtimes.append(_mtime(os.path.join(user_dir, "improve", "self-improving", "permanent", "memory.md")))
    mtimes.append(_mtime(os.path.join(user_dir, "improve", "self-improving", "permanent", "corrections.md")))
    mtimes.append(_dir_max_mtime(os.path.join(user_dir, "improve", "ontology", "permanent"), "*.md"))
    # improve/temporary (临时记忆，注入 system prompt，频繁变化）
    mtimes.append(_dir_max_mtime(os.path.join(user_dir, "improve", "memory", "temporary"), "*.md"))
    mtimes.append(_dir_max_mtime(os.path.join(user_dir, "improve", "self-improving", "temporary"), "*.md"))
    mtimes.append(_dir_max_mtime(os.path.join(user_dir, "improve", "ontology", "temporary"), "*.md"))
    # SESSION-STATE.md (注意：engine.py 从 root 读取，不是 user_dir)
    mtimes.append(_mtime(os.path.join(root, "SESSION-STATE.md")))

    return hash(tuple(mtimes))


def get_prompt_cache_key(root: str, user_dir: str) -> int:
    """获取当前缓存 key（供外部判断缓存是否有效）"""
    return _compute_cache_key(root, user_dir)


def build_cached_system_prompt(root: str, user_dir: str, force: bool = False) -> str:
    """缓存版本的 system prompt 构建。

    Args:
        root: 项目根目录
        user_dir: 用户目录
        force: 强制重建缓存
    """
    cache_key = _compute_cache_key(root, user_dir)

    if not force and user_dir in _cache:
        cached_prompt, old_key = _cache[user_dir]
        if old_key == cache_key:
            return cached_prompt

    # 缓存未命中，调用原函数构建
    from run.engine import build_system_prompt
    prompt = build_system_prompt(root, user_dir)
    _cache[user_dir] = (prompt, cache_key)
    return prompt


def invalidate_prompt_cache(user_dir: str = None):
    """使缓存失效。

    Args:
        user_dir: 指定用户目录则只清该用户，None 则清全部
    """
    if user_dir is None:
        _cache.clear()
    else:
        _cache.pop(user_dir, None)
