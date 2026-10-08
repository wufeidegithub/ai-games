"""俄罗斯方块。

操作：← → 移动，↑ 旋转，↓ 加速下落，空格直接落下，P 暂停，Esc 返回。
"""

import random

import pygame

from common.settings import (
    BLOCK_COLORS,
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

# 每种方块用 4x4 的坐标列表描述，坐标 (col, row)
SHAPES: dict[str, list[tuple[int, int]]] = {
    "I": [(0, 1), (1, 1), (2, 1), (3, 1)],
    "O": [(1, 0), (2, 0), (1, 1), (2, 1)],
    "T": [(1, 0), (0, 1), (1, 1), (2, 1)],
    "S": [(1, 0), (2, 0), (0, 1), (1, 1)],
    "Z": [(0, 0), (1, 0), (1, 1), (2, 1)],
    "J": [(0, 0), (0, 1), (1, 1), (2, 1)],
    "L": [(2, 0), (0, 1), (1, 1), (2, 1)],
}

SHAPE_KEYS = list(SHAPES)
# 每消一行得分
SCORE_PER_LINE = 100
# 一次消多行的额外倍率
LINE_BONUS = {1: 1, 2: 3, 3: 5, 4: 8}


def _rotate(cells: list[tuple[int, int]], board_w: int) -> list[tuple[int, int]]:
    """顺时针旋转 90 度（以 4x4 网格中心为轴），并保证不越左边界。"""
    rotated = [(board_w - 1 - r, c) for c, r in cells]
    min_c = min(c for c, _ in rotated)
    if min_c < 0:
        rotated = [(c - min_c, r) for c, r in rotated]
    return rotated


class Tetris:
    def __init__(self) -> None:
        self.board: list[list[int]] = [[0] * GRID_COLS for _ in range(GRID_ROWS)]
        self.score = 0
        self.lines = 0
        self.over = False
        self.paused = False
        self.fall_ms = 500
        self.acc = 0
        self._spawn()

    # ---------- 方块管理 ----------
    def _spawn(self) -> None:
        key = random.choice(SHAPE_KEYS)
        self.piece_key = key
        self.piece = list(SHAPES[key])
        self.color = BLOCK_COLORS[SHAPE_KEYS.index(key) % len(BLOCK_COLORS)]
        self.px = (GRID_COLS - 4) // 2
        self.py = 0
        if self._collide(self.piece, self.px, self.py):
            self.over = True

    def _collide(self, cells, px: int, py: int) -> bool:
        for c, r in cells:
            x, y = px + c, py + r
            if x < 0 or x >= GRID_COLS or y >= GRID_ROWS:
                return True
            if y >= 0 and self.board[y][x]:
                return True
        return False

    def move(self, dx: int) -> None:
        if not self._collide(self.piece, self.px + dx, self.py):
            self.px += dx

    def rotate(self) -> None:
        rotated = _rotate(self.piece, 4)
        # 贴墙时左右微调，避免旋转失败
        for kick in (0, -1, 1, -2, 2):
            if not self._collide(rotated, self.px + kick, self.py):
                self.piece = rotated
                self.px += kick
                return

    def step(self) -> None:
        """下落一格，落地则固定并生成新方块。"""
        if not self._collide(self.piece, self.px, self.py + 1):
            self.py += 1
            return
        self._lock()

    def hard_drop(self) -> None:
        while not self._collide(self.piece, self.px, self.py + 1):
            self.py += 1
        self._lock()

    def _lock(self) -> None:
        for c, r in self.piece:
            y, x = self.py + r, self.px + c
            if 0 <= y < GRID_ROWS and 0 <= x < GRID_COLS:
                self.board[y][x] = SHAPE_KEYS.index(self.piece_key) + 1
        self._clear_lines()
        if not self.over:
            self._spawn()

    def _clear_lines(self) -> None:
        kept = [row for row in self.board if any(v == 0 for v in row)]
        cleared = GRID_ROWS - len(kept)
        if cleared:
            self.board = [[0] * GRID_COLS for _ in range(cleared)] + kept
            self.lines += cleared
            self.score += SCORE_PER_LINE * LINE_BONUS.get(cleared, cleared)
            # 越消越快
            self.fall_ms = max(90, 500 - self.lines * 12)

    def ghost_y(self) -> int:
        """落点预览的行号。"""
        gy = self.py
        while not self._collide(self.piece, self.px, gy + 1):
            gy += 1
        return gy


def _draw_block(screen, col, row, color, inset=1):
    rect = pygame.Rect(
        col * CELL_SIZE + inset,
        row * CELL_SIZE + inset,
        CELL_SIZE - inset * 2,
        CELL_SIZE - inset * 2,
    )
    pygame.draw.rect(screen, color, rect, border_radius=3)


def run() -> None:
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("俄罗斯方块")
    clock = pygame.time.Clock()

    font_large = pygame.font.Font(None, FONT_SIZE_LARGE)
    font_normal = pygame.font.Font(None, FONT_SIZE_NORMAL)
    font_small = pygame.font.Font(None, FONT_SIZE_SMALL)

    game = Tetris()
    panel_x = GRID_COLS * CELL_SIZE + 24
    running = True

    while running:
        dt = clock.tick(FPS)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return
            if event.type != pygame.KEYDOWN:
                continue

            key = event.key
            if key == pygame.K_ESCAPE:
                return
            if key == pygame.K_r:
                game = Tetris()
                continue
            if key == pygame.K_p:
                game.paused = not game.paused
                continue
            if game.over or game.paused:
                continue

            if key == pygame.K_LEFT:
                game.move(-1)
            elif key == pygame.K_RIGHT:
                game.move(1)
            elif key == pygame.K_UP:
                game.rotate()
            elif key == pygame.K_DOWN:
                game.step()
            elif key == pygame.K_SPACE:
                game.hard_drop()

        if not game.over and not game.paused:
            game.acc += dt
            if game.acc >= game.fall_ms:
                game.acc = 0
                game.step()

        # ---------- 绘制 ----------
        screen.fill(COLOR_BG)

        for c in range(GRID_COLS + 1):
            pygame.draw.line(screen, COLOR_GRID, (c * CELL_SIZE, 0), (c * CELL_SIZE, GRID_ROWS * CELL_SIZE))
        for r in range(GRID_ROWS + 1):
            pygame.draw.line(screen, COLOR_GRID, (0, r * CELL_SIZE), (GRID_COLS * CELL_SIZE, r * CELL_SIZE))

        # 已固定的方块
        for r in range(GRID_ROWS):
            for c in range(GRID_COLS):
                v = game.board[r][c]
                if v:
                    _draw_block(screen, c, r, BLOCK_COLORS[(v - 1) % len(BLOCK_COLORS)])

        if not game.over:
            # 落点预览
            gy = game.ghost_y()
            for c, r in game.piece:
                if gy + r >= 0:
                    _draw_block(screen, game.px + c, gy + r, COLOR_PANEL)

            # 当前方块
            for c, r in game.piece:
                if game.py + r >= 0:
                    _draw_block(screen, game.px + c, game.py + r, game.color)

        # 信息面板
        screen.blit(font_large.render("俄罗斯方块", True, COLOR_TEXT), (panel_x, 30))
        screen.blit(font_normal.render(f"得分  {game.score}", True, COLOR_TEXT), (panel_x, 100))
        screen.blit(font_normal.render(f"消行  {game.lines}", True, COLOR_TEXT), (panel_x, 136))

        if game.over:
            screen.blit(font_normal.render("游戏结束", True, COLOR_DANGER), (panel_x, 210))
            screen.blit(font_small.render("按 R 重开", True, COLOR_TEXT_DIM), (panel_x, 244))
        elif game.paused:
            screen.blit(font_normal.render("已暂停", True, COLOR_ACCENT), (panel_x, 210))

        for i, line in enumerate(["← →  移动", "↑     旋转", "↓     加速", "空格 直落", "P     暂停", "Esc  返回"]):
            screen.blit(font_small.render(line, True, COLOR_TEXT_DIM), (panel_x, WINDOW_HEIGHT - 190 + i * 26))

        pygame.display.flip()


if __name__ == "__main__":
    pygame.init()
    run()
    pygame.quit()
