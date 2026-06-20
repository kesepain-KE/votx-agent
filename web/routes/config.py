"""用户配置路由"""
import copy
import json
import os
import traceback

from flask import jsonify, request, session as flask_session

from web.server import app
from web.session import require_session


def _mask_api_key(config: dict) -> dict:
    """脱敏 provider.api_key — 仅保留前 5 位 + 后 4 位"""
    cfg = copy.deepcopy(config)
    provider = cfg.get("provider", {})
    api_key = provider.get("api_key", "")
    if api_key and len(api_key) > 10:
        provider["api_key"] = api_key[:5] + "***" + api_key[-4:]
    return cfg


@app.route("/api/config")
def api_get_config():
    """处理 api_get_config 相关逻辑。"""
    session_data, err, code = require_session()
    if err:
        return err, code

    user_dir = session_data["user_dir"]
    config_path = os.path.join(user_dir, "config.json")

    try:
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)
        # 脱敏 api_key
        config = _mask_api_key(config)
        return jsonify(config)
    except Exception as e:
        return jsonify({"error": f"读取配置失败: {e}"}), 500


@app.route("/api/provider-capabilities")
def api_provider_capabilities():
    """返回当前 provider 的能力检测结果（自动检测 vs 手动覆盖）。"""
    session_data, err, code = require_session()
    if err:
        return err, code

    provider = session_data.get("provider")
    user_dir = session_data.get("user_dir", "")
    user_config = session_data.get("user_config", {})

    # 读取磁盘上的 override（可能比内存中的 user_config 更新）
    override = None
    if user_dir:
        config_path = os.path.join(user_dir, "config.json")
        try:
            with open(config_path, encoding="utf-8") as f:
                config = json.load(f)
            override = (config.get("provider", {}) or {}).get("capabilities_override")
        except Exception:
            pass

    # 自动检测结果：用不含 override 的临时 provider 探测
    detected = []
    if provider:
        try:
            from provider.factory import create_provider
            temp_config = copy.deepcopy(user_config)
            if "capabilities_override" in temp_config.get("provider", {}):
                del temp_config["provider"]["capabilities_override"]
            temp_provider = create_provider(temp_config)
            detected = sorted(temp_provider.capabilities())
        except Exception:
            pass

    effective = sorted(provider.capabilities()) if provider else []

    return jsonify({
        "mode": "manual" if override is not None else "auto",
        "detected": detected,
        "effective": effective,
        "override": override,
    })


@app.route("/api/config", methods=["POST"])
def api_update_config():
    """处理 api_update_config 相关逻辑。"""
    session_data, err, code = require_session()
    if err:
        return err, code

    data = request.get_json() or {}
    user_dir = session_data["user_dir"]
    config_path = os.path.join(user_dir, "config.json")
    user_name_val = session_data["user_name"]

    try:
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)

        # 顶层字段: task_plan
        if "accept_task" in data:
            tp = config.setdefault("task_plan", {})
            tp["accept_task"] = bool(data["accept_task"])

        # 工具超时设置
        if "tool_timeout" in data:
            tool_cfg = config.setdefault("tool", {})
            tool_cfg["tool_timeout"] = int(data["tool_timeout"])

        provider = config.setdefault("provider", {})

        # Provider 字段白名单
        allowed = {"type", "model", "api_key", "base_url", "stream",
                   "timeout",
                   "vision_model", "audio_transcription_model",
                   "image_generation_model", "image_edit_model",
                   "speech_generation_model", "speech_to_speech_model",
                   "video_generation_model"}
        for key in allowed & data.keys():
            provider[key] = data[key]

        # capabilities_override 特殊处理
        if "capabilities_override" in data:
            val = data["capabilities_override"]
            if val is None or val == "auto":
                provider.pop("capabilities_override", None)
            elif isinstance(val, list):
                from provider.base import VALID_CAPABILITIES
                valid = VALID_CAPABILITIES
                provider["capabilities_override"] = [c for c in val if c in valid]
            else:
                return jsonify({"error": "capabilities_override 必须为 null 或数组"}), 400

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

        # 关键字段变更 → 重建 Provider
        critical = {"type", "api_key", "base_url", "capabilities_override",
                    "vision_model", "audio_transcription_model",
                    "image_generation_model", "image_edit_model",
                    "speech_generation_model", "speech_to_speech_model",
                    "video_generation_model"}
        if critical & data.keys():
            from provider.factory import create_provider
            try:
                new_provider = create_provider(
                    config, session_data.get("core_config")
                )
                session_data["provider"] = new_provider
                session_data["user_config"] = config
            except Exception as e:
                return jsonify({"error": f"Provider 重建失败: {e}"}), 400
        else:
            # 非关键字段直接更新内存属性
            provider_obj = session_data.get("provider")
            if provider_obj:
                for key in allowed & data.keys():
                    setattr(provider_obj, key, data[key])

        # 工具超时变更 → 同步更新 tool_runner
        if "tool_timeout" in data:
            session_data["user_config"] = config
            tr = session_data.get("tool_runner")
            if tr:
                tr.tool_timeout = int(data["tool_timeout"])

        return jsonify({"ok": True})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"保存配置失败: {e}"}), 500
