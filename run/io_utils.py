"""原子写和 JSONL 工具"""
import json
import os
import gzip
import tempfile
from pathlib import Path


def atomic_write_text(path, text):
    """原子写文本文件：写临时文件 → flush → fsync → os.replace"""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    # 在同目录创建临时文件
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix="." + p.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, str(p))
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def atomic_write_json(path, data, indent=2):
    """原子写 JSON 文件"""
    text = json.dumps(data, ensure_ascii=False, indent=indent)
    atomic_write_text(path, text)


def atomic_write_gzip(path, text):
    """原子写 gzip 文件"""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix="." + p.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            with gzip.GzipFile(fileobj=f, mode="wb") as gz:
                gz.write(text.encode("utf-8"))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, str(p))
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def append_jsonl(path, entry):
    """追加一行 JSONL"""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    with open(str(p), "a", encoding="utf-8") as f:
        f.write(line)
        f.flush()
        os.fsync(f.fileno())


def read_json_safe(path, default=None):
    """安全读 JSON，损坏时返回 default"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default
