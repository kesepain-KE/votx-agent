"""用户配置路由"""
import json
import os
import traceback

from flask import jsonify, request, session as flask_session

from web.server import app
from web.session import get_session, get_active_user


@app.route("/api/config")
def api_get_config():
    user_name = flask_session.get("user_name") or get_active_user()
    session_data = get_session(user_name)
    if not session_data or not session_data.get("chat"):
        return jsonify({"error": "未选择用户"}), 400

    user_dir = session_data["user_dir"]
    config_path = os.path.join(user_dir, "config.json")

    try:
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)
        return jsonify(config)
    except Exception as e:
        return jsonify({"error": f"读取配置失败: {e}"}), 500


@app.route("/api/config", methods=["POST"])
def api_update_config():
    user_name = flask_session.get("user_name") or get_active_user()
    session_data = get_session(user_name)
    if not session_data or not session_data.get("chat"):
        return jsonify({"error": "未选择用户"}), 400

    data = request.get_json() or {}
    user_dir = session_data["user_dir"]
    config_path = os.path.join(user_dir, "config.json")
    user_name_val = session_data["user_name"]

    try:
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)

        provider = config.setdefault("provider", {})

        # Provider 字段白名单
        allowed = {"type", "api_style", "model", "api_key", "base_url", "think", "stream",
                   "timeout", "max_tokens", "thinking"}
        for key in allowed & data.keys():
            provider[key] = data[key]

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

        # 关键字段变更 → 重建 Provider（切换协议 / api_style / 换 key / 换地址）
        critical = {"type", "api_style", "api_key", "base_url"}
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

        return jsonify({"ok": True})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"保存配置失败: {e}"}), 500
