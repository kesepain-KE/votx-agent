import json

from message.config import load_config
from message.identity import IdentityStore
from message.permissions import message_mentions_bot, onebot_text, split_message
from message.push_queue import PushQueue


def test_empty_message_config_disables_router(tmp_path):
    message_dir = tmp_path / "message"
    message_dir.mkdir()
    (message_dir / "config.json").write_text("", encoding="utf-8")

    cfg = load_config(str(tmp_path))

    assert cfg["enabled"] is False
    assert cfg["platforms"]["onebot"]["enabled"] is False


def test_identity_resolves_bound_onebot_user(tmp_path):
    cfg = {
        "admins": ["kesepain"],
        "platforms": {
            "onebot": {
                "bound_users": {
                    "qq:123456": "kesepain",
                }
            }
        },
    }

    identity = IdentityStore(str(tmp_path), cfg).resolve_onebot("123456")

    assert identity["internal_user"] == "kesepain"
    assert identity["role"] == "admin"


def test_onebot_text_strips_bot_at_from_cq_message():
    msg = {
        "raw_message": "[CQ:at,qq=10000] /cron list",
        "message": "[CQ:at,qq=10000] /cron list",
    }

    assert message_mentions_bot(msg, "10000") is True
    assert onebot_text(msg, "10000") == "/cron list"


def test_onebot_text_supports_array_message():
    msg = {
        "message": [
            {"type": "at", "data": {"qq": "10000"}},
            {"type": "text", "data": {"text": " /plan list"}},
        ]
    }

    assert message_mentions_bot(msg, "10000") is True
    assert onebot_text(msg, "10000") == "/plan list"


def test_push_queue_round_trip(tmp_path):
    queue = PushQueue(str(tmp_path), "message/push_queue")

    task_id = queue.enqueue({
        "type": "message",
        "platform": "onebot",
        "chat_type": "private",
        "chat_id": "123456",
        "message": "hello",
    })

    pending = queue.pending()
    assert [item["id"] for item in pending] == [task_id]

    queue.complete(task_id, {"ok": True})
    assert queue.pending() == []

    data = json.loads((tmp_path / "message" / "push_queue" / f"{task_id}.json").read_text(encoding="utf-8"))
    assert data["status"] == "completed"


def test_split_message_respects_limit():
    chunks = split_message("abcdef", 2)

    assert chunks == ["ab", "cd", "ef"]
