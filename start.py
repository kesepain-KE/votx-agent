import os
import subprocess
import sys

root = os.path.dirname(__file__)

# 列出所有用户
users_dir = os.path.join(root, "users")
user_list = sorted(os.listdir(users_dir))
print("请选择当前用户:")
for i, name in enumerate(user_list, 1):
    print(f"{i}: {name}")

# 获取用户选择
try:
    idx = int(input("请输入选择: ")) - 1
    selected = user_list[idx]
except (ValueError, IndexError):
    print("无效选择")
    sys.exit(1)

user_dir = os.path.join(users_dir, selected)
print(f"已加载用户: {selected}")

# 调用 main.py，传递用户路径（main.py 自行校验 config/soul）
subprocess.run(
    [sys.executable, os.path.join(root, "main.py")],
    env={**os.environ, "KESEPAIN_USER_DIR": user_dir},
)
