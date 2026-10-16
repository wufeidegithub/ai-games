#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
live_wallpaper.py —— Windows 真·动态壁纸（零第三方引擎、零额外依赖）

原理
----
Windows 桌面其实是两层：Progman（管图标）+ 一个藏在后面的 WorkerW 窗口。
向 Progman 发送未公开消息 0x052C 会让它裂出一个新的 WorkerW，
再把我们自己的窗口 SetParent 到那个 WorkerW 上 —— 于是窗口就"贴"在
桌面图标下面、所有普通窗口上面，成为真正的动态壁纸。
Wallpaper Engine / Lively 用的也是这套机制。

四种动效
--------
aurora    极光流彩    多层正弦流场，青紫渐变，最省 CPU
plasma    等离子波纹  经典 plasma，暖色流动
starfield 星空穿梭    粒子透视飞行 + 暗蓝星云
photo     照片慢推    读取 cache 里的壁纸图片做 Ken Burns 推近+淡入淡出

常用命令
--------
python live_wallpaper.py --start                  后台启动（默认 aurora）
python live_wallpaper.py --start --effect photo   后台启动照片慢推
python live_wallpaper.py --stop                   停止，恢复正常桌面
python live_wallpaper.py --list                   列出所有动效
python live_wallpaper.py --demo 10                前台只跑 10 秒（自测用）
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path

import numpy as np
from PIL import Image

# ---------------------------------------------------------------- 常量

BASE_DIR = Path(__file__).resolve().parent
CACHE_DIR = BASE_DIR / "cache"
CONFIG_PATH = BASE_DIR / "live_config.json"
PID_PATH = BASE_DIR / "live.pid"

CLASS_NAME = "DailyWallpaperLiveClass"
WINDOW_TITLE = "DailyWallpaperLive"

MW = 0x0113   # WM_TIMER
MP = 0x000F   # WM_PAINT
ME = 0x0014   # WM_ERASEBKGND
MD = 0x0002   # WM_DESTROY
MC = 0x0010   # WM_CLOSE
MDC = 0x007E  # WM_DISPLAYCHANGE

TIMER_FRAME = 1
TIMER_WATCH = 2
WATCH_MS = 4000

WS_POPUP = 0x80000000
WS_VISIBLE = 0x10000000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SRCCOPY = 0x00CC0020
HALFTONE = 4
DIB_RGB_COLORS = 0

DEFAULT_CONFIG = {
    "effect": "aurora",
    "fps": 30,
    "photo_fps": 24,        # 照片慢推 CPU 更重，单独降一档更稳
    "field_scale": 0.25,    # 流场类动效的渲染倍率（越小越快）
    "photo_seconds": 14.0,  # 照片慢推：每张停留秒数
    "photo_fade": 2.0,      # 照片切换的淡入淡出秒数
    "photo_folder": "",     # 留空则用 wallpaper 的 cache 目录
}

# ---------------------------------------------------------------- Win32

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

try:
    winmm = ctypes.WinDLL("winmm")
    winmm.timeBeginPeriod.argtypes = [wintypes.UINT]
    winmm.timeBeginPeriod.restype = wintypes.UINT
    winmm.timeEndPeriod.argtypes = [wintypes.UINT]
    winmm.timeEndPeriod.restype = wintypes.UINT
except Exception:                       # pragma: no cover
    winmm = None


def timer_precision(on: bool) -> None:
    """系统计时器默认 15.6ms，会把 33ms 向上取整成 46.9ms。
    提到 1ms 才能拿到真正的高帧率。"""
    if winmm is None:
        return
    try:
        if on:
            winmm.timeBeginPeriod(1)
        else:
            winmm.timeEndPeriod(1)
    except Exception:
        pass

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT,
                             wintypes.WPARAM, wintypes.LPARAM)
ENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


class PAINTSTRUCT(ctypes.Structure):
    _fields_ = [
        ("hdc", wintypes.HDC),
        ("fErase", wintypes.BOOL),
        ("rcPaint", wintypes.RECT),
        ("fRestore", wintypes.BOOL),
        ("fIncUpdate", wintypes.BOOL),
        ("rgbReserved", ctypes.c_byte * 32),
    ]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", wintypes.POINT),
    ]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]


def _decl():
    u, g, k = user32, gdi32, kernel32
    u.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    u.FindWindowW.restype = wintypes.HWND
    u.FindWindowExW.argtypes = [wintypes.HWND, wintypes.HWND,
                                wintypes.LPCWSTR, wintypes.LPCWSTR]
    u.FindWindowExW.restype = wintypes.HWND
    u.SendMessageTimeoutW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM,
                                      wintypes.LPARAM, wintypes.UINT, wintypes.UINT,
                                      ctypes.POINTER(ctypes.c_ulonglong)]
    u.SendMessageTimeoutW.restype = wintypes.LPARAM
    u.EnumWindows.argtypes = [ENUMPROC, wintypes.LPARAM]
    u.EnumWindows.restype = wintypes.BOOL
    u.SetParent.argtypes = [wintypes.HWND, wintypes.HWND]
    u.SetParent.restype = wintypes.HWND
    u.GetParent.argtypes = [wintypes.HWND]
    u.GetParent.restype = wintypes.HWND
    u.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    u.GetAncestor.restype = wintypes.HWND
    u.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                               ctypes.c_int, ctypes.c_int, wintypes.UINT]
    u.SetWindowPos.restype = wintypes.BOOL
    u.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
    u.RegisterClassW.restype = wintypes.ATOM
    u.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR,
                                  wintypes.DWORD, ctypes.c_int, ctypes.c_int,
                                  ctypes.c_int, ctypes.c_int, wintypes.HWND,
                                  wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
    u.CreateWindowExW.restype = wintypes.HWND
    u.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM,
                                 wintypes.LPARAM]
    u.DefWindowProcW.restype = LRESULT
    u.GetMessageW.argtypes = [ctypes.POINTER(MSG), wintypes.HWND,
                              wintypes.UINT, wintypes.UINT]
    u.GetMessageW.restype = wintypes.BOOL
    u.PeekMessageW.argtypes = [ctypes.POINTER(MSG), wintypes.HWND, wintypes.UINT,
                               wintypes.UINT, wintypes.UINT]
    u.PeekMessageW.restype = wintypes.BOOL
    u.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM,
                               wintypes.LPARAM]
    u.PostMessageW.restype = wintypes.BOOL
    u.BeginPaint.argtypes = [wintypes.HWND, ctypes.POINTER(PAINTSTRUCT)]
    u.BeginPaint.restype = wintypes.HDC
    u.EndPaint.argtypes = [wintypes.HWND, ctypes.POINTER(PAINTSTRUCT)]
    u.EndPaint.restype = wintypes.BOOL
    u.GetDC.argtypes = [wintypes.HWND]
    u.GetDC.restype = wintypes.HDC
    u.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    u.ReleaseDC.restype = ctypes.c_int
    u.DestroyWindow.argtypes = [wintypes.HWND]
    u.DestroyWindow.restype = wintypes.BOOL
    u.IsWindow.argtypes = [wintypes.HWND]
    u.IsWindow.restype = wintypes.BOOL
    u.SetTimer.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.LPVOID]
    u.SetTimer.restype = wintypes.UINT
    u.GetSystemMetrics.argtypes = [ctypes.c_int]
    u.GetSystemMetrics.restype = ctypes.c_int
    g.CreateCompatibleDC.argtypes = [wintypes.HDC]
    g.CreateCompatibleDC.restype = wintypes.HDC
    g.CreateDIBSection.argtypes = [wintypes.HDC, ctypes.POINTER(BITMAPINFO),
                                   wintypes.UINT, ctypes.POINTER(ctypes.c_void_p),
                                   wintypes.HANDLE, wintypes.DWORD]
    g.CreateDIBSection.restype = wintypes.HBITMAP
    g.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
    g.SelectObject.restype = wintypes.HGDIOBJ
    g.BitBlt.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                         ctypes.c_int, wintypes.HDC, ctypes.c_int, ctypes.c_int,
                         wintypes.DWORD]
    g.BitBlt.restype = wintypes.BOOL
    g.StretchBlt.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                             ctypes.c_int, wintypes.HDC, ctypes.c_int, ctypes.c_int,
                             ctypes.c_int, ctypes.c_int, wintypes.DWORD]
    g.StretchBlt.restype = wintypes.BOOL
    g.SetStretchBltMode.argtypes = [wintypes.HDC, ctypes.c_int]
    g.SetStretchBltMode.restype = ctypes.c_int
    g.SetBrushOrgEx.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int,
                                wintypes.LPPOINT]
    g.SetBrushOrgEx.restype = wintypes.BOOL
    g.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    g.DeleteObject.restype = wintypes.BOOL
    g.DeleteDC.argtypes = [wintypes.HDC]
    g.DeleteDC.restype = wintypes.BOOL
    k.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
    k.GetModuleHandleW.restype = wintypes.HMODULE


_decl()


def set_dpi_aware() -> None:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)   # PER_MONITOR_AWARE
    except Exception:
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    try:
        with open(BASE_DIR / "live.log", "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def find_workerw(send_msg: bool = True) -> int:
    """拿到桌面图标下面那层 WorkerW 的句柄。

    send_msg=False 时不发 0x052C —— 这条消息每发一次就可能多造一个
    WorkerW，已经贴了壁纸窗口之后随便发会把它的父窗口挤掉。
    """
    progman = user32.FindWindowW("Progman", None)
    if not progman:
        return 0
    if send_msg:
        res = ctypes.c_ulonglong(0)
        user32.SendMessageTimeoutW(progman, 0x052C, 0, 0, 0x0002, 1000,
                                   ctypes.byref(res))

    found = []

    def cb(hwnd, _):
        if user32.FindWindowExW(hwnd, None, "SHELLDLL_DefView", None):
            found.append(user32.FindWindowExW(None, hwnd, "WorkerW", None))
        return True

    user32.EnumWindows(ENUMPROC(cb), 0)
    for h in found:
        if h:
            return h
    return progman   # 兜底：直接贴到 Progman 上


# ---------------------------------------------------------------- 帧缓冲

class DIB:
    """一块可以被 numpy 填数据、再 BitBlt 到窗口的内存位图。"""

    def __init__(self, w: int, h: int):
        self.w, self.h = w, h
        self.size = w * h * 4
        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = w
        bmi.bmiHeader.biHeight = -h          # 负数 = 自上而下
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = 0      # BI_RGB
        self.dc = gdi32.CreateCompatibleDC(None)
        ptr = ctypes.c_void_p()
        self.bmp = gdi32.CreateDIBSection(self.dc, ctypes.byref(bmi),
                                          DIB_RGB_COLORS, ctypes.byref(ptr), None, 0)
        if not self.bmp or not ptr.value:
            raise OSError("CreateDIBSection 失败")
        self.ptr = ptr.value
        gdi32.SelectObject(self.dc, self.bmp)

    def write(self, data: bytes) -> None:
        if len(data) != self.size:
            raise ValueError(f"帧大小不符：{len(data)} != {self.size}")
        ctypes.memmove(self.ptr, data, self.size)

    def blit(self, hdc, dw: int = 0, dh: int = 0) -> None:
        """把这块位图贴到目标 DC；尺寸不同时用 GDI 拉伸（比 numpy 放大快得多）。"""
        if not dw or not dh or (dw == self.w and dh == self.h):
            gdi32.BitBlt(hdc, 0, 0, self.w, self.h, self.dc, 0, 0, SRCCOPY)
            return
        gdi32.SetStretchBltMode(hdc, HALFTONE)
        gdi32.SetBrushOrgEx(hdc, 0, 0, None)
        gdi32.StretchBlt(hdc, 0, 0, dw, dh, self.dc, 0, 0, self.w, self.h, SRCCOPY)

    def free(self) -> None:
        try:
            gdi32.DeleteObject(self.bmp)
            gdi32.DeleteDC(self.dc)
        except Exception:
            pass


# ---------------------------------------------------------------- 动效

_BGRX_OK = None


def to_bgrx(img: Image.Image) -> bytes:
    """PIL 图 → 桌面 DIB 需要的 BGRX 字节流。"""
    global _BGRX_OK
    img = img.convert("RGB")
    if _BGRX_OK is None:
        try:
            img.tobytes("raw", "BGRX")
            _BGRX_OK = True
        except Exception:
            _BGRX_OK = False
    if _BGRX_OK:
        return img.tobytes("raw", "BGRX")
    a = np.asarray(img)
    out = np.empty(a.shape[:2] + (4,), np.uint8)
    out[..., 0] = a[..., 2]
    out[..., 1] = a[..., 1]
    out[..., 2] = a[..., 0]
    out[..., 3] = 255
    return out.tobytes()


def make_lut(stops) -> np.ndarray:
    """(位置0~1, RGB) 列表 → 256 级 BGRA 查找表，可直接给索引数组上色。"""
    xs = np.array([s[0] for s in stops], dtype=np.float32)
    cs = np.array([s[1] for s in stops], dtype=np.float32)
    t = np.linspace(0.0, 1.0, 256, dtype=np.float32)
    lut = np.empty((256, 4), dtype=np.uint8)
    lut[:, 0] = np.interp(t, xs, cs[:, 2])   # B
    lut[:, 1] = np.interp(t, xs, cs[:, 1])   # G
    lut[:, 2] = np.interp(t, xs, cs[:, 0])   # R
    lut[:, 3] = 255
    return lut


class FieldEffect:
    """流场类动效：低分辨率算标量场 → 查色表 → 放大到全屏。"""

    label = "流场"
    stops: list = []

    def __init__(self, w: int, h: int, scale: float = 0.25):
        self.w, self.h = w, h
        self.sw = max(4, int(w * scale))
        self.sh = max(4, int(h * scale))
        self.lut = make_lut(self.stops)
        aspect = w / h
        xs = np.linspace(0.0, aspect, self.sw, dtype=np.float32)
        ys = np.linspace(0.0, 1.0, self.sh, dtype=np.float32)
        self.X = xs[None, :]
        self.Y = ys[:, None]
        self.out_w, self.out_h = self.sw, self.sh   # 交给 GDI 拉伸到全屏
        self.setup()

    def setup(self) -> None:
        pass

    def field(self, t: float) -> np.ndarray:      # pragma: no cover - 子类实现
        raise NotImplementedError

    def frame(self, t: float) -> bytes:
        idx = np.clip(self.field(t) * 255.0, 0.0, 255.0).astype(np.uint8)
        return self.lut[idx].tobytes()


class Aurora(FieldEffect):
    label = "极光流彩"
    stops = [
        (0.00, (4, 8, 26)), (0.28, (16, 44, 96)), (0.50, (20, 126, 150)),
        (0.70, (58, 198, 164)), (0.87, (150, 235, 205)), (1.00, (236, 252, 246)),
    ]

    def field(self, t):
        a = np.sin(self.X * 6.0 + t * 0.60)
        b = np.sin(self.Y * 4.0 - t * 0.45)
        c = np.sin((self.X + self.Y * 1.6) * 3.1 + t * 0.90)
        d = np.sin((self.X * 1.4 - self.Y) * 4.3 - t * 0.50)
        return (a + b + c + d) * 0.125 + 0.5


class Plasma(FieldEffect):
    label = "等离子波纹"
    stops = [
        (0.00, (10, 6, 40)), (0.24, (72, 20, 122)), (0.48, (192, 42, 132)),
        (0.70, (240, 110, 58)), (0.88, (250, 202, 92)), (1.00, (255, 250, 224)),
    ]

    def setup(self):
        cx, cy = self.X.mean(), self.Y.mean()
        r = np.sqrt((self.X - cx) ** 2 + (self.Y - cy) ** 2)
        self.R = (r / max(r.max(), 1e-6)).astype(np.float32)

    def field(self, t):
        a = np.sin(self.X * 4.0 + t * 0.80)
        b = np.sin(self.Y * 5.0 - t * 0.60)
        c = np.sin(self.R * 11.0 - t * 1.60)
        d = np.sin((self.X + self.Y) * 2.5 + t * 0.40)
        return (a + b + c + d) * 0.125 + 0.5


class Starfield:
    label = "星空穿梭"

    def __init__(self, w, h, scale=0.5, count=420):
        self.w, self.h = w, h
        self.sw = max(8, int(w * scale))
        self.sh = max(8, int(h * scale))
        self.out_w, self.out_h = self.sw, self.sh
        rng = np.random.default_rng(20260920)
        self.px = rng.uniform(0.0, 1.0, count).astype(np.float32)
        self.py = rng.uniform(0.0, 1.0, count).astype(np.float32)
        self.pz = rng.uniform(0.02, 1.0, count).astype(np.float32)
        self.ps = rng.uniform(0.5, 1.7, count).astype(np.float32)
        # 背景：中心略亮的暗蓝星云
        xs = np.linspace(0, 1, self.sw, dtype=np.float32)
        ys = np.linspace(0, 1, self.sh, dtype=np.float32)
        r = np.sqrt((xs[None, :] - 0.5) ** 2 + (ys[:, None] - 0.45) ** 2)
        glow = np.clip(1.0 - r * 1.5, 0.0, 1.0) ** 2
        self.bg = np.stack([glow * 0.055, glow * 0.070, glow * 0.150], axis=-1)

    def frame(self, t: float) -> bytes:
        canvas = np.array(self.bg, dtype=np.float32, copy=True)
        z = (self.pz + t * 0.030 * self.ps) % 1.0
        z = np.clip(z, 0.02, 1.0)
        spread = 0.10 + z * 1.55
        sx = 0.5 + (self.px - 0.5) * spread
        sy = 0.5 + (self.py - 0.5) * spread
        bright = np.clip(0.18 + z * 1.30, 0.0, 1.0)
        mask = (sx >= 0.0) & (sx < 1.0) & (sy >= 0.0) & (sy < 1.0)   # 飞出画面就丢弃
        xi = np.clip((sx[mask] * self.sw).astype(np.int32), 0, self.sw - 1)
        yi = np.clip((sy[mask] * self.sh).astype(np.int32), 0, self.sh - 1)
        bright = bright[mask]
        flat = canvas.reshape(-1, 3)
        fidx = yi * self.sw + xi
        for ch, wgt in enumerate((0.78, 0.86, 1.0)):
            np.maximum.at(flat[:, ch], fidx, bright * wgt)
        rgb = np.clip(canvas * 255.0, 0, 255).astype(np.uint8)
        return to_bgrx(Image.fromarray(rgb))


class PhotoRoll:
    """把壁纸图片做出缓慢推近 + 平移 + 交叉淡入的纪录片感。"""

    label = "照片慢推"
    MAG = 1.30   # 工作图比屏幕大 30%，留出推近和平移的余量

    def __init__(self, w, h, folder: Path, hold=14.0, fade=2.0):
        self.w, self.h = w, h
        self.out_w, self.out_h = w, h
        self.hold = max(4.0, float(hold))
        self.fade = min(max(0.5, float(fade)), self.hold * 0.5)
        self.ww, self.wh = int(w * self.MAG), int(h * self.MAG)
        self.items: list[Image.Image] = []

        folder = Path(folder)
        if folder.is_dir():
            files = [p for p in folder.iterdir()
                     if p.is_file() and p.suffix.lower() in
                     {".jpg", ".jpeg", ".png", ".bmp"}]
            files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            for p in files[:12]:
                try:
                    self.items.append(self._cover(Image.open(p)))
                except Exception:
                    continue

    def _cover(self, im: Image.Image) -> Image.Image:
        im = im.convert("RGB")
        sw, sh = im.size
        k = max(self.ww / sw, self.wh / sh)
        nw, nh = max(self.ww, int(sw * k)), max(self.wh, int(sh * k))
        im = im.resize((nw, nh), Image.LANCZOS)
        left = (nw - self.ww) // 2
        top = (nh - self.wh) // 2
        return im.crop((left, top, left + self.ww, top + self.wh))

    def _ken(self, im: Image.Image, p: float) -> Image.Image:
        p = p % 1.0
        z = 1.0 + (self.MAG - 1.0) * p
        cw = int(self.ww / z)
        ch = int(self.wh / z)
        slack_x = self.ww - cw
        slack_y = self.wh - ch
        import math
        cx = slack_x * (0.5 + 0.42 * math.sin(2 * math.pi * p))
        cy = slack_y * (0.5 + 0.42 * math.cos(2 * math.pi * p * 0.8))
        box = (int(cx), int(cy), int(cx) + cw, int(cy) + ch)
        return im.crop(box).resize((self.w, self.h), Image.BILINEAR)

    def frame(self, t: float) -> bytes:
        n = len(self.items)
        if n == 0:
            raise RuntimeError("没有可用图片")
        period = self.hold
        idx = int(t // period) % n
        local = t - (t // period) * period
        cur = self._ken(self.items[idx], t / (period * 6.0))
        if n > 1 and local > period - self.fade:
            alpha = (local - (period - self.fade)) / self.fade
            nxt = self._ken(self.items[(idx + 1) % n], t / (period * 6.0))
            return to_bgrx(Image.blend(cur, nxt, min(alpha, 1.0)))
        return to_bgrx(cur)


EFFECTS = {
    "aurora": (Aurora, "极光流彩 —— 青紫渐变流场，最省资源"),
    "plasma": (Plasma, "等离子波纹 —— 暖色流动，经典 plasma"),
    "starfield": (Starfield, "星空穿梭 —— 粒子透视飞行"),
    "photo": (PhotoRoll, "照片慢推 —— 壁纸图片 Ken Burns 推近+淡入淡出"),
}


def build_effect(name: str, cfg: dict, w: int, h: int):
    cls = EFFECTS.get(name, (Aurora, ""))[0]
    if cls is FieldEffect or issubclass(cls, FieldEffect):
        return cls(w, h, scale=float(cfg.get("field_scale") or 0.25))
    if cls is Starfield:
        return cls(w, h, scale=0.5)
    if cls is PhotoRoll:
        folder = cfg.get("photo_folder") or CACHE_DIR
        return cls(w, h, folder, hold=cfg.get("photo_seconds") or 14.0,
                   fade=cfg.get("photo_fade") or 2.0)
    return cls(w, h)


# ---------------------------------------------------------------- 引擎

class Engine:
    def __init__(self, effect_name: str, cfg: dict, fps: int, seconds: float | None):
        self.cfg = cfg
        self.effect_name = effect_name
        self.fps = max(5, min(60, int(fps)))
        self.seconds = seconds
        self.w = user32.GetSystemMetrics(78) or user32.GetSystemMetrics(0)
        self.h = user32.GetSystemMetrics(79) or user32.GetSystemMetrics(1)
        self.ox = user32.GetSystemMetrics(76)
        self.oy = user32.GetSystemMetrics(77)
        self.dib = None
        self.effect = None
        self.screen_hdc = None
        self.hwnd = 0
        self.parent = 0
        self.stopping = False
        self.t0 = time.perf_counter()
        self.frames = 0
        self.first_t = None
        self.last_t = None
        self.cpu_ms = 0.0
        self._proc = WNDPROC(self._wndproc)   # 必须保住引用，否则被 GC 崩溃

    # ---------- 窗口

    def _register(self):
        hinst = kernel32.GetModuleHandleW(None)
        wc = WNDCLASSW()
        wc.style = 0
        wc.lpfnWndProc = self._proc
        wc.cbClsExtra = 0
        wc.cbWndExtra = 0
        wc.hInstance = hinst
        wc.hIcon = None
        wc.hCursor = None
        wc.hbrBackground = None      # 关键：不擦背景，避免闪烁
        wc.lpszMenuName = None
        wc.lpszClassName = CLASS_NAME
        atom = user32.RegisterClassW(ctypes.byref(wc))
        if not atom:
            err = ctypes.get_last_error()
            if err != 1410:          # 1410 = 类已注册，正常
                raise ctypes.WinError(err)
        return hinst

    def create(self) -> None:
        hinst = self._register()
        self.parent = find_workerw()
        if not self.parent:
            raise RuntimeError("找不到桌面 WorkerW，无法注入")
        self.hwnd = user32.CreateWindowExW(
            WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE, CLASS_NAME, WINDOW_TITLE,
            WS_POPUP | WS_VISIBLE, self.ox, self.oy, self.w, self.h,
            None, None, hinst, None)
        if not self.hwnd:
            raise ctypes.WinError(ctypes.get_last_error())
        user32.SetParent(self.hwnd, self.parent)
        user32.SetWindowPos(self.hwnd, None, 0, 0, self.w, self.h,
                            SWP_NOZORDER | SWP_NOACTIVATE)
        self.effect = build_effect(self.effect_name, self.cfg, self.w, self.h)
        self.dib = DIB(self.effect.out_w, self.effect.out_h)
        self.screen_hdc = user32.GetDC(self.hwnd)   # 缓存 DC，别每帧取

    # ---------- 消息

    def _wndproc(self, hwnd, msg, wparam, lparam):
        if msg == MP:
            ps = PAINTSTRUCT()
            hdc = user32.BeginPaint(hwnd, ctypes.byref(ps))
            if self.dib:
                self.dib.blit(hdc, self.w, self.h)
            user32.EndPaint(hwnd, ctypes.byref(ps))
            return 0
        if msg == ME:
            return 1
        if msg == MDC:
            self._resize()
            return 0
        if msg == MC:
            self.stopping = True
            user32.DestroyWindow(hwnd)
            return 0
        if msg == MD:
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _render(self, hwnd) -> None:
        if not self.dib:
            return
        t = time.perf_counter() - self.t0
        begin = time.perf_counter()
        try:
            self.dib.write(self.effect.frame(t))
        except RuntimeError:
            return
        if self.screen_hdc:
            self.dib.blit(self.screen_hdc, self.w, self.h)
        else:
            hdc = user32.GetDC(hwnd)
            self.dib.blit(hdc, self.w, self.h)
            user32.ReleaseDC(hwnd, hdc)
        self.cpu_ms += (time.perf_counter() - begin) * 1000.0
        self.frames += 1
        if self.first_t is None:
            self.first_t = t
        self.last_t = t
        if self.seconds and t >= self.seconds:
            self.stopping = True
            user32.PostMessageW(hwnd, MC, 0, 0)

    def _watch(self) -> None:
        """Explorer 重启或桌面重组时，把窗口重新贴回桌面底层。"""
        GA_PARENT = 1
        ok = user32.IsWindow(self.parent) and \
            user32.GetAncestor(self.hwnd, GA_PARENT) == self.parent
        if not ok:
            self.parent = find_workerw(send_msg=True)
            user32.SetParent(self.hwnd, self.parent)
            user32.SetWindowPos(self.hwnd, None, self.ox, self.oy, self.w, self.h,
                                SWP_NOZORDER | SWP_NOACTIVATE)
            log(f"watch: 重新贴回桌面 WorkerW={self.parent}")

    def _resize(self) -> None:
        w = user32.GetSystemMetrics(78) or user32.GetSystemMetrics(0)
        h = user32.GetSystemMetrics(79) or user32.GetSystemMetrics(1)
        if (w, h) == (self.w, self.h):
            return
        self.w, self.h = w, h
        self.ox = user32.GetSystemMetrics(76)
        self.oy = user32.GetSystemMetrics(77)
        if self.dib:
            self.dib.free()
        self.effect = build_effect(self.effect_name, self.cfg, w, h)
        self.dib = DIB(self.effect.out_w, self.effect.out_h)
        if self.screen_hdc:
            user32.ReleaseDC(self.hwnd, self.screen_hdc)
        self.screen_hdc = user32.GetDC(self.hwnd)
        user32.SetWindowPos(self.hwnd, None, self.ox, self.oy, w, h,
                            SWP_NOZORDER | SWP_NOACTIVATE)

    def run(self) -> None:
        """自控帧循环：不用 WM_TIMER，因为它会被系统计时器精度量化
        （33ms 会被向上取整成 46.9ms，帧率直接腰斩）。"""
        timer_precision(True)
        msg = MSG()
        PM_REMOVE = 0x0001
        WM_QUIT = 0x0012
        interval = 1.0 / self.fps
        next_at = time.perf_counter()
        last_watch = next_at
        alive = True
        try:
            while alive:
                while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
                    if msg.message == WM_QUIT:
                        alive = False
                        break
                    user32.TranslateMessage(ctypes.byref(msg))
                    user32.DispatchMessageW(ctypes.byref(msg))
                if not alive:
                    break
                now = time.perf_counter()
                if now >= next_at:
                    self._render(self.hwnd)
                    next_at += interval
                    if next_at < now:               # 落后太多就重新对齐
                        next_at = now + interval
                else:
                    time.sleep(min(next_at - now, 0.004))
                if now - last_watch >= WATCH_MS / 1000.0:
                    self._watch()
                    last_watch = now
        finally:
            timer_precision(False)
        if self.screen_hdc and self.hwnd:
            user32.ReleaseDC(self.hwnd, self.screen_hdc)
            self.screen_hdc = None
        if self.dib:
            self.dib.free()
            self.dib = None


# ---------------------------------------------------------------- 控制

def load_cfg() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                cfg.update(data)
        except (OSError, json.JSONDecodeError):
            pass
    return cfg


def save_default_cfg() -> None:
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(
            json.dumps(DEFAULT_CONFIG, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8")


def pythonw() -> str:
    exe = Path(sys.executable)
    cand = exe.with_name("pythonw.exe")
    return str(cand if cand.exists() else exe)


def existing_window() -> int:
    """找正在运行的壁纸窗口。绝不发 0x052C。
    注意 SetParent 之后它是 WorkerW 的子窗口，FindWindowW 搜顶层找不到。"""
    result = []

    def cb(hwnd, _):
        buf = ctypes.create_unicode_buffer(64)
        user32.GetClassNameW(hwnd, buf, 64)
        if buf.value in ("WorkerW", "Progman"):
            hwnd2 = user32.FindWindowExW(hwnd, None, CLASS_NAME, None)
            if hwnd2:
                result.append(hwnd2)
        return True

    user32.EnumWindows(ENUMPROC(cb), 0)
    if result:
        return result[0]
    return user32.FindWindowW(CLASS_NAME, None)   # 兜底：还没贴上去的瞬间


def cmd_start(cfg: dict, effect: str, fps: int) -> int:
    if existing_window():
        say("· 动态壁纸已经在运行了。想换效果先执行 --stop")
        return 0
    script = BASE_DIR / "live_wallpaper.py"
    args = [pythonw(), str(script), "--run",
            "--effect", effect, "--fps", str(fps)]
    flags = 0x00000008 | 0x08000000           # DETACHED_PROCESS | CREATE_NO_WINDOW
    proc = subprocess.Popen(args, creationflags=flags, close_fds=True,
                            cwd=str(BASE_DIR))
    PID_PATH.write_text(str(proc.pid), encoding="utf-8")
    # pythonw 冷启动 + numpy/PIL 导入要一两秒，耐心轮询
    for _ in range(60):
        time.sleep(0.25)
        if existing_window():
            break
    if existing_window():
        say(f"✓ 动态壁纸已启动（{EFFECTS.get(effect, ('', ''))[0].label}，{fps} fps）")
        say("  停止：python live_wallpaper.py --stop")
        return 0
    say("× 启动失败，可能是动效初始化出错")
    say("  用 python live_wallpaper.py --demo 5 --effect " + effect + " 前台跑一下看报错")
    return 1


def cmd_stop() -> int:
    hwnd = existing_window()
    if hwnd:
        user32.PostMessageW(hwnd, MC, 0, 0)
        for _ in range(30):
            time.sleep(0.1)
            if not existing_window():
                break
        say("✓ 动态壁纸已停止，桌面已恢复")
    else:
        say("· 没有正在运行的动态壁纸")
    if PID_PATH.exists():
        try:
            PID_PATH.unlink()
        except OSError:
            pass
    return 0


def say(msg: str = "") -> None:
    try:
        print(msg)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"
        print(msg.encode(enc, "replace").decode(enc, "replace"))


def cmd_demo(cfg: dict, effect: str, fps: int, seconds: float) -> int:
    engine = Engine(effect, cfg, fps, seconds)
    engine.create()
    ready = time.perf_counter()
    say(f"→ 前台运行 {effect}，{fps} fps，{seconds} 秒后自动停止…")
    engine.run()
    span = (engine.last_t - engine.first_t) if engine.first_t else 0.0
    real = (engine.frames - 1) / span if span > 0.02 else 0.0
    per = engine.cpu_ms / engine.frames if engine.frames else 0.0
    say(f"✓ 结束。{engine.frames} 帧 / {span:.2f}s 渲染区间 = {real:.1f} fps"
        f"（每帧 CPU {per:.1f} ms，启动耗时 {(ready - engine.t0):.2f}s）")
    return 0


def cmd_run(cfg: dict, effect: str, fps: int) -> int:
    """前台跑引擎。若窗口被外力销毁（比如 Explorer 重启），自动重贴。"""
    for attempt in range(20):
        engine = Engine(effect, cfg, fps, None)
        try:
            engine.create()
        except Exception as exc:
            log(f"create 失败（第 {attempt + 1} 次）：{exc!r}")
            time.sleep(3)
            continue
        engine.run()
        if engine.stopping:
            log("run: 主动停止")
            return 0
        log(f"run: 窗口被销毁（第 {attempt + 1} 次），3 秒后重新贴回")
        time.sleep(3)
    return 0


def cmd_list() -> None:
    say("可用动效：")
    for name, (cls, desc) in EFFECTS.items():
        say(f"  {name:<10} {desc}")
    say("\n用法：python live_wallpaper.py --start --effect <名字>")


# ---------------------------------------------------------------- 入口

def build_parser():
    p = argparse.ArgumentParser(prog="live_wallpaper.py",
                                description="Windows 真·动态壁纸")
    p.add_argument("--start", action="store_true", help="后台启动")
    p.add_argument("--stop", action="store_true", help="停止并恢复桌面")
    p.add_argument("--run", action="store_true", help="前台运行（内部用）")
    p.add_argument("--demo", type=float, metavar="SECONDS",
                   help="前台运行指定秒数后退出，用于自测")
    p.add_argument("--effect", default=None, help="动效名，见 --list")
    p.add_argument("--fps", type=int, default=None, help="帧率，5~60")
    p.add_argument("--list", action="store_true", help="列出所有动效")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.list:
        cmd_list()
        return 0

    set_dpi_aware()
    save_default_cfg()
    cfg = load_cfg()
    effect = args.effect or cfg.get("effect") or "aurora"
    if effect not in EFFECTS:
        say(f"× 未知动效：{effect}")
        cmd_list()
        return 2
    fps = args.fps or int(
        (cfg.get("photo_fps") or 24) if effect == "photo"
        else (cfg.get("fps") or 30))

    if args.stop:
        return cmd_stop()
    if args.start:
        return cmd_start(cfg, effect, fps)
    if args.demo:
        return cmd_demo(cfg, effect, fps, args.demo)
    if args.run:
        return cmd_run(cfg, effect, fps)
    build_parser().print_help()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        try:
            print(f"发生错误：{exc}")
        except Exception:
            pass
        sys.exit(1)
