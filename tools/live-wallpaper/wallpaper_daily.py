#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
wallpaper_daily.py —— 每天自动更换 Windows 桌面壁纸

三种图源（可在 config.json 里切换）：
  bing    : 必应每日一图（4K 原图，每天自动不同）
  picsum  : Picsum 随机高清图（按日期取种子，同一天结果稳定）
  folder  : 你本地图片文件夹，轮流换，全部轮完才开始下一轮

常用命令：
  python wallpaper_daily.py                  按配置换一次（同一天重复运行会自动跳过）
  python wallpaper_daily.py --force          强制换一张
  python wallpaper_daily.py --dry-run        只下载不设置，用来试网络
  python wallpaper_daily.py --source folder  临时改用本地文件夹
  python wallpaper_daily.py --style fit      临时指定填充方式
  python wallpaper_daily.py --list           查看最近更换记录
  python wallpaper_daily.py --status         查看当前状态
  python wallpaper_daily.py --install-startup    开机自动检查（推荐，免管理员）
  python wallpaper_daily.py --install-task       注册每天 09:00 的计划任务
  python wallpaper_daily.py --uninstall-all      卸载上面两种自动化

作者：WorkBuddy
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import random
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path

# ---------------------------------------------------------------- 常量与配置

APP_NAME = "DailyWallpaper"
BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
STATE_PATH = BASE_DIR / "state.json"
CACHE_DIR = BASE_DIR / "cache"
LOG_PATH = BASE_DIR / "wallpaper.log"

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) WallpaperDaily/1.0"

DEFAULT_CONFIG = {
    "source": "bing",           # bing | picsum | folder
    "fallback_source": "picsum",  # 主图源失败时的备用图源，留空表示不兜底
    "bing_market": "zh-CN",     # zh-CN / en-US / ja-JP ...
    "bing_index": 0,            # 0=今天 1=昨天 ... 必应保留最近 8 天
    "folder": "",               # source=folder 时的图片文件夹（支持绝对路径）
    "picsum_seed": "",          # 留空则用当天日期做种子
    "width": 1920,
    "height": 1080,
    "style": "fill",            # center | tile | stretch | fit | fill | span
    "gap": 0,                   # 桌面图标间距（像素）
    "task_name": APP_NAME,
    "task_time": "09:00",       # 计划任务触发时间
    "cache_keep_days": 30,      # 缓存图片保留天数
}

# 注册表 WallpaperStyle / TileWallpaper 取值
STYLES = {
    "center":  ("0",  "0"),   # 居中
    "tile":    ("0",  "1"),   # 平铺
    "stretch": ("2",  "0"),   # 拉伸
    "fit":     ("6",  "0"),   # 适应
    "fill":    ("10", "0"),   # 填充（默认，最常用）
    "span":    ("22", "0"),   # 跨屏
}

SPI_SETDESKWALLPAPER = 0x0014
SPI_SETDESKICONSPACING = 0x0025
SPIF_UPDATEINIFILE = 0x01
SPIF_SENDWININICHANGE = 0x02

QUIET = False


def say(msg: str = "") -> None:
    """安全的打印：遇到控制台编码不支持时降级，不让脚本崩掉。"""
    if QUIET:
        return
    try:
        print(msg)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"
        print(msg.encode(enc, "replace").decode(enc, "replace"))


def log(msg: str) -> None:
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


# ---------------------------------------------------------------- 配置与状态

def load_config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_PATH.exists():
        try:
            user_cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(user_cfg, dict):
                cfg.update(user_cfg)
        except (OSError, json.JSONDecodeError) as exc:
            say(f"! config.json 读取失败（{exc}），本次使用默认配置")
    return cfg


def save_default_config(force: bool = False) -> None:
    if CONFIG_PATH.exists() and not force:
        say(f"config.json 已存在，未覆盖：{CONFIG_PATH}")
        return
    CONFIG_PATH.write_text(
        json.dumps(DEFAULT_CONFIG, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    say(f"已生成默认配置：{CONFIG_PATH}")


def load_state() -> dict:
    if STATE_PATH.exists():
        try:
            data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data.setdefault("used_keys", [])
                data.setdefault("records", [])
                return data
        except (OSError, json.JSONDecodeError):
            pass
    return {"last_date": "", "last_file": "", "last_source": "", "last_title": "",
            "used_keys": [], "records": []}


def save_state(state: dict) -> None:
    state["used_keys"] = state.get("used_keys", [])[-1000:]
    state["records"] = state.get("records", [])[-200:]
    STATE_PATH.write_text(
        json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


# ---------------------------------------------------------------- 设置壁纸

def set_wallpaper_style(style: str) -> None:
    if os.name != "nt":
        return
    values = STYLES.get(style)
    if not values:
        values = STYLES["fill"]
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop", 0,
                        winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, "WallpaperStyle", 0, winreg.REG_SZ, values[0])
        winreg.SetValueEx(key, "TileWallpaper", 0, winreg.REG_SZ, values[1])


def set_icon_spacing(gap: int) -> None:
    if os.name != "nt" or not gap:
        return
    ctypes.windll.user32.SystemParametersInfoW(
        SPI_SETDESKICONSPACING, int(gap), None, SPIF_UPDATEINIFILE
    )


def apply_wallpaper(path: Path, style: str = "fill", gap: int = 0) -> None:
    if os.name != "nt":
        raise RuntimeError("设置桌面壁纸目前只支持 Windows")
    path = path.resolve()
    if not path.exists():
        raise FileNotFoundError(f"图片不存在：{path}")

    set_wallpaper_style(style)
    ok = ctypes.windll.user32.SystemParametersInfoW(
        SPI_SETDESKWALLPAPER, 0, str(path),
        SPIF_UPDATEINIFILE | SPIF_SENDWININICHANGE,
    )
    if not ok:
        raise ctypes.WinError(ctypes.get_last_error())
    if gap:
        set_icon_spacing(gap)


# ---------------------------------------------------------------- 图片获取

def http_get(url: str, timeout: int = 25) -> bytes:
    req = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def fetch_bing(cfg: dict, used: set[str]) -> dict:
    mkt = cfg.get("bing_market") or "zh-CN"
    idx = int(cfg.get("bing_index") or 0)
    api = ("https://www.bing.com/HPImageArchive.aspx"
           f"?format=js&idx={idx}&n=1&mkt={mkt}")
    data = json.loads(http_get(api).decode("utf-8", "replace"))
    images = data.get("images") or []
    if not images:
        raise RuntimeError("必应接口没有返回图片")
    img = images[0]
    urlbase = img.get("urlbase") or ""
    if not urlbase:
        raise RuntimeError("必应接口缺少 urlbase 字段")
    return {
        "key": "bing:" + str(img.get("fullstartdate") or urlbase.lstrip("/")),
        "url": "https://www.bing.com" + urlbase + "_UHD.jpg",
        "title": img.get("title") or "必应每日一图",
        "desc": (img.get("copyright") or "").strip(),
        "ext": ".jpg",
    }


def fetch_picsum(cfg: dict, used: set[str]) -> dict:
    width = int(cfg.get("width") or 1920)
    height = int(cfg.get("height") or 1080)
    seed = str(cfg.get("picsum_seed") or date.today().isoformat())
    return {
        "key": f"picsum:{seed}",
        "url": f"https://picsum.photos/seed/{seed}/{width}/{height}",
        "title": f"Picsum · {seed}",
        "desc": "随机高清图（picsum.photos）",
        "ext": ".jpg",
    }


def fetch_folder(cfg: dict, used: set[str]) -> dict:
    raw = (cfg.get("folder") or "").strip()
    if not raw:
        raise RuntimeError("配置里的 folder 为空，请填一个图片文件夹路径")
    root = Path(os.path.expandvars(os.path.expanduser(raw)))
    if not root.is_dir():
        raise RuntimeError(f"文件夹不存在：{root}")

    files = sorted(
        p for p in root.rglob("*")
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS
    )
    if not files:
        raise RuntimeError(f"文件夹里没找到图片：{root}")

    def key_of(p: Path) -> str:
        try:
            rel = p.relative_to(root)
        except ValueError:
            rel = p
        return "folder:" + str(rel).replace(os.sep, "/")

    unused = [p for p in files if key_of(p) not in used]
    if not unused:
        # 全部轮完一遍了，清掉该来源的记录重新开始
        used = {k for k in used if not k.startswith("folder:")}
        unused = files
    picked = random.SystemRandom().choice(unused)
    return {
        "key": key_of(picked),
        "local": str(picked),
        "title": picked.stem,
        "desc": str(picked),
        "ext": picked.suffix.lower(),
    }


SOURCES = {"bing": fetch_bing, "picsum": fetch_picsum, "folder": fetch_folder}


def materialize(info: dict, source: str) -> Path:
    """把图片落到 cache 目录，返回本地路径。"""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    raw_key = str(info["key"])
    if raw_key.startswith(source + ":"):
        raw_key = raw_key[len(source) + 1:]          # 文件名里不用再重复来源
    safe = "".join(c if c.isalnum() or c in "-_.@" else "_" for c in raw_key)[:80]
    ext = info.get("ext") or ".jpg"
    dest = CACHE_DIR / f"{source}_{safe}{ext}"

    if info.get("local"):
        src = Path(info["local"])
        if src.resolve() != dest.resolve():
            import shutil
            shutil.copy2(src, dest)
        return dest

    if dest.exists() and dest.stat().st_size > 1024:
        return dest  # 同一天重复运行直接复用

    tmp = dest.with_suffix(dest.suffix + ".part")
    data = http_get(info["url"], timeout=45)
    if len(data) < 1024:
        raise RuntimeError(f"下载内容异常（{len(data)} 字节）")
    tmp.write_bytes(data)
    tmp.replace(dest)
    return dest


def cleanup_cache(keep_days: int) -> None:
    if not keep_days or not CACHE_DIR.is_dir():
        return
    deadline = datetime.now().timestamp() - keep_days * 86400
    for p in CACHE_DIR.iterdir():
        try:
            if p.is_file() and p.stat().st_mtime < deadline:
                p.unlink()
        except OSError:
            pass


# ---------------------------------------------------------------- 主流程

def change_wallpaper(cfg: dict, args) -> int:
    state = load_state()
    today = date.today().isoformat()

    if not args.force and not args.dry_run and state.get("last_date") == today:
        say(f"今天已经换过了：{state.get('last_file')}")
        say("想再换一张就加 --force")
        return 0

    used = set(state.get("used_keys") or [])
    order = [cfg.get("source") or "bing"]
    fb = cfg.get("fallback_source")
    if fb and fb not in order:
        order.append(fb)

    info, source, last_err = None, "", None
    for name in order:
        func = SOURCES.get(name)
        if not func:
            continue
        try:
            say(f"→ 正在从 [{name}] 获取图片…")
            info = func(cfg, used)
            source = name
            break
        except Exception as exc:                      # 网络/接口问题都兜住
            last_err = exc
            say(f"! 图源 [{name}] 失败：{exc}")
            log(f"source {name} failed: {exc}")

    if info is None:
        say(f"× 所有图源都失败了，最后错误：{last_err}")
        log(f"all sources failed: {last_err}")
        return 1

    try:
        path = materialize(info, source)
    except Exception as exc:
        say(f"× 图片保存失败：{exc}")
        log(f"materialize failed: {exc}")
        return 1

    style = args.style or cfg.get("style") or "fill"
    say(f"  图片：{path.name}")
    say(f"  标题：{info.get('title') or '-'}")
    if info.get("desc") and info.get("desc") != info.get("title"):
        say(f"  说明：{info['desc'][:120]}")

    if args.dry_run:
        say("（--dry-run 模式：已下载，未修改桌面）")
        return 0

    try:
        apply_wallpaper(path, style=style, gap=int(cfg.get("gap") or 0))
    except Exception as exc:
        say(f"× 设置壁纸失败：{exc}")
        log(f"apply failed: {exc}")
        return 1

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    state["last_date"] = today
    state["last_file"] = str(path)
    state["last_source"] = source
    state["last_title"] = info.get("title") or ""
    state["used_keys"] = list(used) + [info["key"]]
    state.setdefault("records", []).append(
        {"time": now, "source": source, "title": state["last_title"],
         "file": path.name, "key": info["key"]}
    )
    save_state(state)
    cleanup_cache(int(cfg.get("cache_keep_days") or 0))

    say(f"✓ 桌面壁纸已更新（{style}）")
    log(f"ok source={source} file={path.name}")
    return 0


# ---------------------------------------------------------------- 自动化安装

def startup_dir() -> Path:
    appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData/Roaming")
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def startup_file() -> Path:
    return startup_dir() / f"{APP_NAME}.vbs"


def pythonw() -> str:
    exe = Path(sys.executable)
    cand = exe.with_name("pythonw.exe")   # 用 pythonw 启动，不弹黑窗
    return str(cand if cand.exists() else exe)


def install_startup() -> int:
    if os.name != "nt":
        say("× 只支持 Windows")
        return 1
    d = startup_dir()
    if not d.is_dir():
        say(f"× 找不到启动文件夹：{d}")
        return 1
    script = BASE_DIR / "wallpaper_daily.py"
    vbs = (
        'Set ws = CreateObject("WScript.Shell")\r\n'
        f'ws.Run """{pythonw()}"" ""{script}"" --quiet", 0, False\r\n'
    )
    target = startup_file()
    try:
        target.write_text(vbs, encoding="ascii", errors="ignore")
    except OSError as exc:
        say(f"× 写入失败：{exc}")
        return 1
    say(f"✓ 已设置开机自动检查：{target}")
    say("  每次开机/登录后会检查今天是否换过，没换就自动换一张。")
    say("  （想每天固定时间换，请用 install_task.bat）")
    log("startup installed")
    return 0


def uninstall_startup() -> int:
    target = startup_file()
    if target.exists():
        try:
            target.unlink()
            say(f"✓ 已移除开机自启：{target.name}")
        except OSError as exc:
            say(f"× 删除失败：{exc}")
            return 1
    else:
        say("· 未发现开机自启项，跳过")
    return 0


def run_cmd(cmd: list[str]) -> tuple[int, str]:
    try:
        proc = subprocess.run(cmd, capture_output=True)
    except FileNotFoundError as exc:
        return 1, str(exc)
    out = (proc.stdout or b"").decode("utf-8", "replace").strip()
    err = (proc.stderr or b"").decode("utf-8", "replace").strip()
    return proc.returncode, (out + ("\n" + err if err else "")).strip()


def install_task(cfg: dict) -> int:
    if os.name != "nt":
        say("× 只支持 Windows")
        return 1
    name = cfg.get("task_name") or APP_NAME
    at = cfg.get("task_time") or "09:00"
    script = BASE_DIR / "wallpaper_daily.py"
    tr = f'"{pythonw()}" "{script}" --quiet'
    code, out = run_cmd([
        "schtasks", "/Create", "/TN", name, "/TR", tr,
        "/SC", "DAILY", "/ST", at, "/RL", "LIMITED", "/F",
    ])
    if code != 0:
        say(f"× 创建计划任务失败（返回码 {code}）")
        say(out or "（没有更多信息；可尝试以管理员身份运行）")
        return code
    say(f"✓ 已注册计划任务「{name}」，每天 {at} 自动更换壁纸")
    log(f"task installed at {at}")
    return 0


def uninstall_task(cfg: dict) -> int:
    name = cfg.get("task_name") or APP_NAME
    code, out = run_cmd(["schtasks", "/Delete", "/TN", name, "/F"])
    if code != 0:
        say("· 未发现同名计划任务（或删除失败），跳过")
    else:
        say(f"✓ 已删除计划任务「{name}」")
        log("task removed")
    return 0


def task_status(cfg: dict) -> None:
    name = cfg.get("task_name") or APP_NAME
    code, out = run_cmd(["schtasks", "/Query", "/TN", name, "/V", "/FO", "LIST"])
    if code == 0:
        say(f"计划任务「{name}」状态：")
        say(out)
    else:
        say(f"· 未查询到计划任务「{name}」")
    say(f"开机自启项：{'已安装' if startup_file().exists() else '未安装'}")


# ---------------------------------------------------------------- 展示信息

def show_list(state: dict, limit: int = 10) -> None:
    records = state.get("records") or []
    if not records:
        say("还没有更换记录。")
        return
    say(f"最近 {min(limit, len(records))} 次更换：")
    for rec in reversed(records[-limit:]):
        say(f"  {rec.get('time','')}  [{rec.get('source','')}]  {rec.get('title','')}")


def show_status(cfg: dict, state: dict) -> None:
    say("—— 当前配置 ——")
    say(f"  图源      : {cfg.get('source')}（备用：{cfg.get('fallback_source') or '无'}）")
    if cfg.get("source") == "folder" or cfg.get("folder"):
        say(f"  图片文件夹: {cfg.get('folder') or '（未设置）'}")
    say(f"  填充方式  : {cfg.get('style')}")
    say(f"  计划时间  : {cfg.get('task_time')}")
    say("—— 运行状态 ——")
    say(f"  上次更换  : {state.get('last_date') or '（从未）'}")
    say(f"  上次图片  : {state.get('last_file') or '-'}")
    say(f"  上次标题  : {state.get('last_title') or '-'}")
    say(f"  已用图片  : {len(state.get('used_keys') or [])} 张")
    say(f"  缓存目录  : {CACHE_DIR}")
    say(f"  日志文件  : {LOG_PATH}")
    say(f"  开机自启  : {'已安装' if startup_file().exists() else '未安装'}")


# ---------------------------------------------------------------- 入口

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="wallpaper_daily.py",
        description="每天自动更换 Windows 桌面壁纸",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--source", choices=list(SOURCES), help="本次使用的图源")
    p.add_argument("--style", choices=list(STYLES), help="填充方式")
    p.add_argument("--force", action="store_true", help="今天已换过也强制再换")
    p.add_argument("--dry-run", action="store_true", help="只下载不修改桌面")
    p.add_argument("--quiet", action="store_true", help="不输出信息（供计划任务用）")
    p.add_argument("--init", action="store_true", help="生成默认 config.json")
    p.add_argument("--init-force", action="store_true", help="覆盖生成 config.json")
    p.add_argument("--list", action="store_true", help="查看最近更换记录")
    p.add_argument("--status", action="store_true", help="查看配置与运行状态")
    p.add_argument("--install-startup", action="store_true", help="安装开机自启（推荐）")
    p.add_argument("--uninstall-startup", action="store_true", help="移除开机自启")
    p.add_argument("--install-task", action="store_true", help="注册每天计划任务")
    p.add_argument("--uninstall-task", action="store_true", help="删除计划任务")
    p.add_argument("--task-status", action="store_true", help="查询计划任务状态")
    p.add_argument("--uninstall-all", action="store_true", help="卸载全部自动化")
    return p


def main(argv=None) -> int:
    global QUIET
    args = build_parser().parse_args(argv)
    QUIET = bool(args.quiet)
    cfg = load_config()
    state = load_state()

    if args.init or args.init_force:
        save_default_config(force=args.init_force)
        return 0
    if args.list:
        show_list(state)
        return 0
    if args.status:
        show_status(cfg, state)
        return 0
    if args.task_status:
        task_status(cfg)
        return 0
    if args.install_startup:
        return install_startup()
    if args.uninstall_startup:
        return uninstall_startup()
    if args.install_task:
        return install_task(cfg)
    if args.uninstall_task:
        return uninstall_task(cfg)
    if args.uninstall_all:
        uninstall_startup()
        uninstall_task(cfg)
        return 0

    return change_wallpaper(cfg, args)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as exc:                       # 兜底，避免计划任务里静默失败
        log(f"fatal: {exc!r}")
        try:
            print(f"发生错误：{exc}")
        except Exception:
            pass
        sys.exit(1)
