import ctypes
import sys

def is_admin():
    """检查当前是否以管理员权限运行"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def run_as_admin():
    """请求以管理员权限重新运行程序"""
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, " ".join(sys.argv), None, 1
    )

def check_and_prompt_admin():
    """检查当前权限并在需要时请求管理员权限"""
    if not is_admin():
        run_as_admin()
        sys.exit(0)  # 重新运行后退出当前实例