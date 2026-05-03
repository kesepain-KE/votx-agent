"""用户配置路由"""
import json
import os
import traceback

from flask import jsonify, request

from web.server import app
from web.session import _session


@app.route("/api/config")
def api_get_config():
    if not _session.get("chat"):
        return jsonify({"error": "未选择用户"}), 400

    user_dir = _session["user_dir"]
    config_path = os.path.join(user_dir, "config.json")

    try:
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)
        return jsonify(config)
    except Exception as e:
        return jsonify({"error": f"读取配置失败: {e}"}), 500


@app.route("/api/config", methods=["POST"])
def api_update_config():
    if not _session.get("chat"):
        return jsonify({"error": "未选择用户"}), 400

    data = request.get_json() or {}
    user_dir = _session["user_dir"]
    config_path = os.path.join(user_dir, "config.json")

    try:
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)

        provider = config.setdefault("provider", {})

        if "model" in data:
            provider["model"] = data["model"]
        if "think" in data:
            provider["think"] = bool(data["think"])
        if "stream" in data:
            provider["stream"] = bool(data["stream"])
        if "base_url" in data:
            provider["base_url"] = data["base_url"]
        if "api_key" in data:
            provider["api_key"] = data["api_key"]

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

        # 同步更新内存中的 provider
        provider_obj = _session.get("provider")
        if provider_obj:
            if "model" in data:
                provider_obj.model = data["model"]
            if "think" in data:
                provider_obj.think = bool(data["think"])
            if "stream" in data:
                provider_obj.stream = bool(data["stream"])
            if "base_url" in data:
                provider_obj.base_url = data["base_url"]
            if "api_key" in data:
                provider_obj.api_key = data["api_key"]

        return jsonify({"ok": True})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"保存配置失败: {e}"}), 500
