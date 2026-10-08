"""贪吃蛇。

操作：方向键或 WASD 控制方向，空格暂停，R 重开，Esc 返回菜单。
"""

import random

import pygame

from common.settings import (
    CELL_SIZE,
    COLOR_ACCENT,
    COLOR_BG,
    COLOR_DANGER,
    COLOR_GRID,
    COLOR_PANEL,
    COLOR_TEXT,
    COLOR_TEXT_DIM,
    FONT_SIZE_LARGE,
    FONT_SIZE_NORMAL,
    FONT_SIZE_SMALL,
    FPS,
    GRID_COLS,
    GRID_ROWS,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)

# 初始长度
INIT_LENGTH = 4
# 每吃一个食物加多少分
SCORE_PER_FOOD = 10
# 分数越高越快：每 SCORE_PER_FOOD 分，速度提升一档
SPEEDUP_EVERY = 50


def _random_food(snake: list[tuple[int, int]]) -> tuple[int, int]:
    """在空格子里随机放食物。"""
    free = [
        (c, r)
        for c in range(GRID_COLS)
        for r in range(GRID_ROWS)
        if (c, r) not in snake
    ]
    return random.choice(free) if free else (-1, -1)


def _draw_cell(screen: pygame.Surface, col: int, row: int, color, inset: int = 1) -> None:
    rect = pygame.Rect(
        col * CELL_SIZE + inset,
        row * CELL_SIZE + inset,
        CELL_SIZE - inset * 2,
        CELL_SIZE - inset * 2,
    )
    pygame.draw.rect(screen, color, rect, border_radius=4)


def run() -> None:
    """启动贪吃蛇。返回时表示玩家退回菜单。"""
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("贪吃蛇")
    clock = pygame.time.Clock()

    font_large = pygame.font.Font(None, FONT_SIZE_LARGE)
    font_normal = pygame.font.Font(None, FONT_SIZE_NORMAL)
    font_small = pygame.font.Font(None, FONT_SIZE_SMALL)

    def reset() -> dict:
        center = (GRID_COLS // 2, GRID_ROWS // 2)
        snake = [(center[0] - i, center[1]) for i in range(INIT_LENGTH)]
        return {
            "snake": snake,
            "direction": (1, 0),
            "pending": (1, 0),          # 本帧待生效的方向
            "food": _random_food(snake),
            "score": 0,
            "alive": True,
            "paused": False,
            "move_ms": 140,             # 移动间隔，越小越快
            "acc": 0,
        }

    state = reset()
    running = True

    while running:
        dt = clock.tick(FPS)

        # ---------- 事件 ----------
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return
            if event.type != pygame.KEYDOWN:
                continue

            key = event.key
            if key == pygame.K_ESCAPE:
                return
            if key == pygame.K_r:
                state = reset()
                continue
            if key == pygame.K_SPACE:
                state["paused"] = not state["paused"]
                continue

            if not state["alive"]:
                continue

            # 方向：不允许 180 度掉头
            cur = state["direction"]
            mapping = {
                pygame.K_UP: (0, -1), pygame.K_w: (0, -1),
                pygame.K_DOWN: (0, 1), pygame.K_s: (0, 1),
                pygame.K_LEFT: (-1, 0), pygame.K_a: (-1, 0),
                pygame.K_RIGHT: (1, 0), pygame.K_d: (1, 0),
            }
            want = mapping.get(key)
            if want and (want[0] != -cur[0] or want[1] != -cur[1]):
                state["pending"] = want

        # ---------- 逻辑 ----------
        if state["alive"] and not state["paused"]:
            state["acc"] += dt
            if state["acc"] >= state["move_ms"]:
                state["acc"] = 0
                state["direction"] = state["pending"]

                head = state["snake"][0]
                nx = head[0] + state["direction"][0]
                ny = head[1] + state["direction"][1]

                # 撞墙
                if not (0 <= nx < GRID_COLS and 0 <= ny < GRID_ROWS):
                    state["alive"] = False
                # 咬到自己（尾巴那一格本帧会移开，不算）
                elif (nx, ny) in state["snake"][:-1]:
                    state["alive"] = False
                else:
                    state["snake"].insert(0, (nx, ny))
                    if (nx, ny) == state["food"]:
                        state["score"] += SCORE_PER_FOOD
                        state["food"] = _random_food(state["snake"])
                        # 提速
                        level = state["score"] // SPEEDUP_EVERY
                        state["move_ms"] = max(60, 140 - level * 10)
                    else:
                        state["snake"].pop()

        # ---------- 绘制 ----------
        screen.fill(COLOR_BG)

        for c in range(GRID_COLS + 1):
            pygame.draw.line(screen, COLOR_GRID, (c * CELL_SIZE, 0), (c * CELL_SIZE, GRID_ROWS * CELL_SIZE))
        for r in range(GRID_ROWS + 1):
            pygame.draw.line(screen, COLOR_GRID, (0, r * CELL_SIZE), (GRID_COLS * CELL_SIZE, r * CELL_SIZE))

        fx, fy = state["food"]
        if fx >= 0:
            _draw_cell(screen, fx, fy, COLOR_DANGER, inset=4)

        for i, (cx, cy) in enumerate(state["snake"]):
            color = COLOR_ACCENT if i == 0 else (86, 150, 220)
            _draw_cell(screen, cx, cy, color)

        # 右侧信息面板
        panel_x = GRID_COLS * CELL_SIZE + 24
        screen.blit(font_large.render("贪吃蛇", True, COLOR_TEXT), (panel_x, 30))
        screen.blit(font_normal.render(f"得分  {state['score']}", True, COLOR_TEXT), (panel_x, 100))
        screen.blit(font_normal.render(f"长度  {len(state['snake'])}", True, COLOR_TEXT), (panel_x, 136))

        if not state["alive"]:
            screen.blit(font_normal.render("游戏结束", True, COLOR_DANGER), (panel_x, 210))
            screen.blit(font_small.render("按 R 重开", True, COLOR_TEXT_DIM), (panel_x, 244))
        elif state["paused"]:
            screen.blit(font_normal.render("已暂停", True, COLOR_ACCENT), (panel_x, 210))

        screen.blit(font_small.render("空格 暂停", True, COLOR_TEXT_DIM), (panel_x, WINDOW_HEIGHT - 110))
        screen.blit(font_small.render("R    重开", True, COLOR_TEXT_DIM), (panel_x, WINDOW_HEIGHT - 86))
        screen.blit(font_small.render("Esc  返回", True, COLOR_TEXT_DIM), (panel_x, WINDOW_HEIGHT - 62))

        pygame.display.flip()


if __name__ == "__main__":
    pygame.init()
    run()
    pygame.quit()
