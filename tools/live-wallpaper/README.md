# 每天自动更换桌面壁纸

一个零依赖的 Python 小工具（只用标准库），让 Windows 桌面壁纸每天自动换一张。

## 文件说明

| 文件 | 作用 |
| --- | --- |
| `wallpaper_daily.py` | 主程序，所有功能都在这里 |
| `config.json` | 配置文件：图源、填充方式、定时时间等 |
| `install_startup.bat` | **一键安装开机自启**（推荐，不需要管理员） |
| `install_task.bat` | 一键注册计划任务（每天固定时间换，不需要管理员） |
| `change_now.bat` | 一键立即换一张 |
| `uninstall.bat` | 一键卸载全部自动化 |
| `state.json` | 运行状态：上次换了什么、用过哪些图（自动生成） |
| `cache/` | 下载/复制过来的图片缓存（自动生成，默认保留 30 天） |
| `wallpaper.log` | 运行日志（自动生成） |

## 一分钟上手

1. 双击 `change_now.bat` —— 立刻换一张，先看看效果。
2. 双击 `install_startup.bat` —— 以后每次开机自动检查，今天没换过就换一张。
3. 想让电脑长时间不关机也能每天换，再双击 `install_task.bat`，默认每天 09:00 触发。

> 两个都装也没关系：程序内部有「同一天只换一次」的判定，不会重复折腾。

## 三种图源

改 `config.json` 里的 `source` 即可：

| 值 | 说明 |
| --- | --- |
| `bing` | **默认**。必应每日一图，4K 原图，自带标题和版权说明，每天自动不同 |
| `picsum` | Picsum 随机高清图，按当天日期取种子，同一天结果稳定 |
| `folder` | 你自己的图片文件夹，会轮流换，全部轮完一遍才开始下一轮 |

用本地图片文件夹的话这样配：

```json
{
  "source": "folder",
  "folder": "D:\\壁纸收藏"
}
```

`fallback_source` 是备用图源：主图源挂了（比如没网）会自动切换，默认 `picsum`，想关掉就填 `""`。

## 常用配置项

```json
{
  "source": "bing",              // bing | picsum | folder
  "fallback_source": "picsum",   // 主图源失败时的兜底，留空关闭
  "bing_market": "zh-CN",        // 地区：zh-CN / en-US / ja-JP ...
  "bing_index": 0,               // 0=今天 1=昨天，必应保留最近 8 天
  "folder": "",                  // source=folder 时的图片目录
  "style": "fill",               // center居中|tile平铺|stretch拉伸|fit适应|fill填充|span跨屏
  "gap": 0,                      // 桌面图标间距(像素)，0 表示不动
  "task_time": "09:00",          // 计划任务的触发时间
  "cache_keep_days": 30          // 缓存保留天数，0 表示不清理
}
```

注意：`style` 和 `gap` 会写进注册表，并**影响整个桌面**，不只是本程序换的那张图。

## 命令行用法

想在终端里精细控制，直接跑 `wallpaper_daily.py`：

```bash
python wallpaper_daily.py                  # 按配置换一次（今天换过则跳过）
python wallpaper_daily.py --force          # 强制再换一张
python wallpaper_daily.py --dry-run        # 只下载不设置，用来试网络
python wallpaper_daily.py --source folder  # 临时改用本地文件夹
python wallpaper_daily.py --style fit      # 临时指定填充方式
python wallpaper_daily.py --list           # 看最近 10 次更换记录
python wallpaper_daily.py --status         # 看配置 + 运行状态
python wallpaper_daily.py --task-status    # 查询计划任务状态
python wallpaper_daily.py --uninstall-all  # 卸载全部自动化
```

## 定时任务没装上怎么办

`install_task.bat` 依赖系统自带的 `schtasks`。如果被杀软/安全策略拦住，有两个办法：

- 右键 `install_task.bat` → 以管理员身份运行；
- 或者干脆只用 `install_startup.bat`（走的是启动文件夹，完全不碰 `schtasks`）。

## 想还原

```bash
python wallpaper_daily.py --uninstall-all   # 或双击 uninstall.bat
```

然后手动把桌面壁纸换回你喜欢的那张即可。注册表里的 `WallpaperStyle` 保持 `fill`（填充）不会有什么副作用，如需还原可在「设置 → 个性化 → 背景」里重新选一次。

## 想更进一步

现在的方案是「每天换一张静态壁纸」。如果你要的是真正意义上的**动态壁纸**（视频、动画、粒子效果），那是另一个技术路线（常驻进程 + 渲染窗口贴在桌面层）—— 见下方「动态壁纸」章节，本项目里已经实现了。

---

# 动态壁纸（live_wallpaper.py）

让桌面真的"动起来"——**零第三方引擎、零额外依赖**（只用 Python 标准库 + Win32 API）。

## 原理

Windows 桌面其实是两层：`Progman`（管图标的那个）和一个藏在它后面的 `WorkerW` 窗口。

程序的作法：

1. 向 `Progman` 发送**未公开消息 `0x052C`**，让它裂出一个新的 `WorkerW`；
2. 找到这个 WorkerW 的句柄；
3. 把自己的渲染窗口 `SetParent` 挂到那个 WorkerW 上。

于是窗口就"贴"在桌面图标**下面**、所有普通窗口**上面** —— 成为真正的动态壁纸。

> Wallpaper Engine / Lively 用的也是这套机制。这是 Windows 上唯二靠谱的免驱动方案。

## 四种动效

| 动效 | 名称 | 说明 | CPU 占用 |
|---|---|---|---|
| `aurora` | 极光流彩 | 多层正弦流场，青紫渐变 | **最省**（默认） |
| `plasma` | 等离子波纹 | 经典 plasma 算法，暖色流动 | 中 |
| `starfield` | 星空穿梭 | 粒子透视飞行 + 暗蓝星云 | 中 |
| `photo` | 照片慢推 | 读取 `cache/` 里的壁纸图片，做 Ken Burns 推近 + 淡入淡出 | 低 |

`_preview_*.png` 是四种动效的预览图，可以先看效果再决定用哪个。

## 用法

```bash
python live_wallpaper.py --start                   # 后台启动（默认 aurora）
python live_wallpaper.py --start --effect photo    # 后台启动照片慢推
python live_wallpaper.py --stop                    # 停止，恢复正常桌面
python live_wallpaper.py --list                    # 列出所有动效
python live_wallpaper.py --demo 10                 # 前台跑 10 秒（自测用）
```

参数在 `live_config.json` 里调：

```json
{
  "effect": "aurora",        // 动效名
  "fps": 30,                 // 帧率
  "field_scale": 0.25,       // 流场缩放（越小越细腻，越费 CPU）
  "photo_seconds": 14.0,     // 照片动效：每张停留秒数
  "photo_fade": 2.0,         // 照片动效：淡入淡出时长
  "photo_folder": ""         // 留空则用 cache/ 目录，也可指定自己的图片目录
}
```

## 配套工具

| 文件 | 作用 |
|---|---|
| `_probe_workerw.py` | 探测 WorkerW 窗口句柄，排查"壁纸没贴上"时用 |

---

## 环境要求

- Windows 10 / 11
- Python 3.8+（脚本只用标准库，不需要 pip 装任何东西）
- **照片动效**需要 `cache/` 里有图片，或自行在 `live_config.json` 里指定 `photo_folder`

## 两个模块的关系

| 模块 | 文件 | 做什么 | 是否常驻 |
|---|---|---|---|
| 每日换壁纸 | `wallpaper_daily.py` | 每天自动换一张**静态**壁纸 | 否（定时触发一次即退出） |
| 动态壁纸 | `live_wallpaper.py` | 桌面上跑**动画** | **是**（后台常驻进程） |

两者不冲突，可以同时用：动态壁纸进程负责"动"，每日换壁纸负责给 `photo` 动效提供新素材。

