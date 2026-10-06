"""PyTaskMon Flask entry point"""
from typing import get_args

from flask import Flask, jsonify, render_template, request

import actions
from collector import get_snapshot
from contract import Priority

app = Flask(__name__, template_folder="ui/templates", static_folder="ui/static")

VALID_LEVELS = set(get_args(Priority))
# action ที่ต้องมี confirm
CONFIRM_ACTIONS = {"terminate", "kill"}
SIMPLE_ACTIONS = {"suspend", "resume"}

@app.get("/")
def index():
    return render_template("index.html")

@app.get("/api/snapshot")
def api_snapshot():
    return jsonify(get_snapshot())


def _bad_request(message: str):
    return jsonify({"ok": False, "code": "error", "message": message}), 400


@app.post("/api/action")
def api_action():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _bad_request("ต้องส่งเป็น JSON object")

    pid = data.get("pid")
    # bool เป็น subclass ของ int ใน Python ต้องกันออกเอง
    if not isinstance(pid, int) or isinstance(pid, bool) or pid < 0:
        return _bad_request("pid ต้องเป็นจำนวนเต็มที่ไม่ติดลบ")

    action = data.get("action")

    if action in CONFIRM_ACTIONS:
        confirm = data.get("confirm") is True   # ต้องเป็น true จริงๆ เท่านั้น
        result = getattr(actions, action)(pid, confirm)
    elif action in SIMPLE_ACTIONS:
        result = getattr(actions, action)(pid)
    elif action == "set_priority":
        level = data.get("level")
        if level not in VALID_LEVELS:
            return _bad_request(f"level ต้องเป็นหนึ่งใน {sorted(VALID_LEVELS)}")
        result = actions.set_priority(pid, level)
    else:
        return _bad_request("action ไม่รู้จัก")

    return jsonify(result)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=False)