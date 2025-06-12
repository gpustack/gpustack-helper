import ctypes
import sys


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def run_as_admin():
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, " ".join(sys.argv), None, 1
    )


def check_and_prompt_admin():
    if not is_admin():
        run_as_admin()
        sys.exit(0)  # 重新运行后退出当前实例
