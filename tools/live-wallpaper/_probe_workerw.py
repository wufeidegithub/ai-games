# -*- coding: utf-8 -*-
"""探测：WorkerW 注入是否可行 + 屏幕参数"""
import ctypes
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)

user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.FindWindowW.restype = wintypes.HWND
user32.FindWindowExW.argtypes = [wintypes.HWND, wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.FindWindowExW.restype = wintypes.HWND
user32.SendMessageTimeoutW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM,
                                       wintypes.LPARAM, wintypes.UINT, wintypes.UINT,
                                       ctypes.POINTER(ctypes.c_ulonglong)]
user32.SendMessageTimeoutW.restype = wintypes.LPARAM
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception as exc:
    print("DPI 设置失败:", exc)

SM = {"虚拟桌面原点X": 76, "虚拟桌面原点Y": 77, "虚拟桌面宽": 78, "虚拟桌面高": 79,
      "主屏宽": 0, "主屏高": 1, "显示器数量": 80}
for name, idx in SM.items():
    print(f"{name}: {user32.GetSystemMetrics(idx)}")

progman = user32.FindWindowW("Progman", None)
print("Progman 句柄:", progman)
if not progman:
    raise SystemExit("找不到 Progman，桌面 shell 异常")

result = ctypes.c_ulonglong(0)
user32.SendMessageTimeoutW(progman, 0x052C, 0, 0, 0x0002, 1000, ctypes.byref(result))
print("已发送 0x052C 通知，返回值:", result.value)

found = []


def enum_proc(hwnd, lparam):
    if user32.FindWindowExW(hwnd, None, "SHELLDLL_DefView", None):
        sibling = user32.FindWindowExW(None, hwnd, "WorkerW", None)
        buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, buf, 256)
        found.append((hwnd, sibling, buf.value))
    return True


ENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
user32.EnumWindows.argtypes = [ENUMPROC, wintypes.LPARAM]
user32.EnumWindows(ENUMPROC(enum_proc), 0)

print("含 SHELLDLL_DefView 的窗口:")
for hwnd, sibling, cls in found:
    print(f"  hwnd={hwnd}  class={cls}  其后的 WorkerW={sibling}")

if any(s for _, s, _ in found):
    print("\n结论：可以拿到桌面底层的 WorkerW，注入方案可行 ✓")
elif any(cls == "WorkerW" for _, _, cls in found):
    print("\n结论：只拿到 WorkerW 自身，可用 Progman 兜底 ✓")
else:
    print("\n结论：未找到 WorkerW，可能需要在 Explorer 重启后重试")
