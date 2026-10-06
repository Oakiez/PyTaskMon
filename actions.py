"""เลือก implementation ของ actions ตาม OS (UI เรียกผ่านไฟล์นี้เท่านั้น)"""
import sys

if sys.platform == "win32":
    from actions_windows import (
        terminate, kill, suspend, resume, set_priority, is_protected,
    )
else:
    from actions_unix import (
        terminate, kill, suspend, resume, set_priority, is_protected,
    )

__all__ = ["terminate", "kill", "suspend", "resume", "set_priority", "is_protected"]