"""游戏注册表。

每个游戏模块暴露一个 run() 函数，主菜单遍历这里来生成选项，
新增游戏只要在 load_games() 里加一行。
"""

from typing import Callable, TypedDict


class GameInfo(TypedDict):
    key: str                     # 唯一标识，用于 settings.GAME_ORDER
    title: str                   # 菜单显示名
    description: str             # 一句话说明
    run: Callable[[], None]      # 启动函数


def load_games() -> dict[str, GameInfo]:
    """延迟导入，避免某个游戏报错导致整个菜单起不来。"""
    from games.snake import run as run_snake
    from games.tetris import run as run_tetris

    return {
        "snake": {
            "key": "snake",
            "title": "贪吃蛇",
            "description": "方向键控制，吃到食物变长，撞墙或咬到自己结束",
            "run": run_snake,
        },
        "tetris": {
            "key": "tetris",
            "title": "俄罗斯方块",
            "description": "左 右 移动，上 旋转，下 加速，空格直落",
            "run": run_tetris,
        },
    }
