"""原子写、JSONL 和跨平台文本/子进程 IO 工具。"""
import json
import locale
import os
import time
import gzip
import tempfile
from pathlib import Path


def text_encoding_candidates(encoding="utf-8"):
    """返回文本读取编码候选；新文件 UTF-8，Windows 旧文件可回退 GBK/locale。"""
    candidates = []
    preferred = locale.getpreferredencoding(False) or ""
    for enc in (encoding, "utf-8-sig", "utf-8", "gbk", preferred):
        if enc and enc not in candidates:
            candidates.append(enc)
    return candidates


def read_text_fallback(path, encoding="utf-8"):
    """读取文本文件，优先 UTF-8，再回退 UTF-8 BOM/GBK/系统编码。"""
    p = Path(path)
    last_error = None
    for enc in text_encoding_candidates(encoding):
        try:
            return p.read_text(encoding=enc), enc
        except UnicodeDecodeError as e:
            last_error = e
    raise last_error or UnicodeDecodeError("utf-8", b"", 0, 1, "decode failed")


def write_text_utf8(path, text):
    """用 UTF-8 写文本文件，并自动创建父目录。"""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def utf8_subprocess_env(env=None):
    """返回偏向 UTF-8 的子进程环境，避免 Windows 控制台代码页影响输出。"""
    merged = dict(os.environ if env is None else env)
    merged.setdefault("PYTHONUTF8", "1")
    merged["PYTHONIOENCODING"] = "utf-8"
    return merged


def decode_subprocess_output(data, encoding="utf-8"):
    """解码子进程 bytes 输出；优先 UTF-8，再回退系统编码。"""
    if data is None:
        return ""
    if isinstance(data, str):
        return data
    for enc in text_encoding_candidates(encoding):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode(encoding or "utf-8", errors="replace")


def atomic_write_text(path, text):
    """原子写文本文件：写临时文件 → flush → fsync → os.replace（含 Windows 重试）"""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    # 在同目录创建临时文件
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix="." + p.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        # Windows 上目标文件可能被杀毒软件/索引服务锁定，重试 3 次
        for attempt in range(3):
            try:
                os.replace(tmp, str(p))
                return
            except PermissionError:
                if attempt < 2:
                    time.sleep(0.05)
                else:
                    raise
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
