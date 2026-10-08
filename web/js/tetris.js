/* ============================================================
   俄罗斯方块 —— 网页版
   画布高度比宽度大，所以按行数换算格子尺寸
   ============================================================ */

(function () {
  const COLS = 10;
  const ROWS = 20;

  const SHAPES = {
    I: [[0, 1], [1, 1], [2, 1], [3, 1]],
    O: [[1, 0], [2, 0], [1, 1], [2, 1]],
    T: [[1, 0], [0, 1], [1, 1], [2, 1]],
    S: [[1, 0], [2, 0], [0, 1], [1, 1]],
    Z: [[0, 0], [1, 0], [1, 1], [2, 1]],
    J: [[0, 0], [0, 1], [1, 1], [2, 1]],
    L: [[2, 0], [0, 1], [1, 1], [2, 1]],
  };
  const KEYS = Object.keys(SHAPES);

  const SCORE_PER_LINE = 100;
  const LINE_BONUS = { 1: 1, 2: 3, 3: 5, 4: 8 };
  const BASE_FALL = 500;
  const MIN_FALL = 90;

  /** 顺时针旋转 90 度，并保证不越左边界 */
  function rotate(cells) {
    const rotated = cells.map(([c, r]) => [3 - r, c]);
    const minC = Math.min(...rotated.map(([c]) => c));
    return minC < 0 ? rotated.map(([c, r]) => [c - minC, r]) : rotated;
  }

  class TetrisGame {
    constructor(canvas) {
      this.canvas = canvas;
      this.ctx = canvas.getContext('2d');
      // 按高度算格子，保持方块为正方形
      this.cell = canvas.height / ROWS;
      this.offsetX = (canvas.width - this.cell * COLS) / 2;

      this.onScoreChange = null;
      this.onGameOver = null;
      this.onPauseChange = null;

      this.reset();
    }

    reset() {
      this.board = Array.from({ length: ROWS }, () => new Array(COLS).fill(0));
      this.score = 0;
      this.lines = 0;
      this.over = false;
      this.paused = false;
      this.acc = 0;
      this.fallInterval = BASE_FALL;

      this.spawn();
      this.bindKeys();

      if (this.onScoreChange) this.onScoreChange();
      this.draw();
    }

    spawn() {
      const key = KEYS[Game.randInt(KEYS.length)];
      this.pieceKey = key;
      this.piece = SHAPES[key].map((c) => c.slice());
      this.color = Game.COLORS.blocks[KEYS.indexOf(key) % Game.COLORS.blocks.length];
      this.px = Math.floor((COLS - 4) / 2);
      this.py = 0;

      if (this.collide(this.piece, this.px, this.py)) {
        this.over = true;
        if (this.onGameOver) this.onGameOver(this.score);
      }
    }

    collide(cells, px, py) {
      return cells.some(([c, r]) => {
        const x = px + c;
        const y = py + r;
        if (x < 0 || x >= COLS || y >= ROWS) return true;
        return y >= 0 && this.board[y][x] !== 0;
      });
    }

    move(dx) {
      if (!this.over && !this.paused && !this.collide(this.piece, this.px + dx, this.py)) {
        this.px += dx;
      }
    }

    rotate() {
      if (this.over || this.paused) return;
      const rotated = rotate(this.piece);
      // 贴墙时左右微调
      for (const kick of [0, -1, 1, -2, 2]) {
        if (!this.collide(rotated, this.px + kick, this.py)) {
          this.piece = rotated;
          this.px += kick;
          return;
        }
      }
    }

    step() {
      if (!this.collide(this.piece, this.px, this.py + 1)) {
        this.py += 1;
      } else {
        this.lock();
      }
    }

    hardDrop() {
      if (this.over || this.paused) return;
      while (!this.collide(this.piece, this.px, this.py + 1)) this.py += 1;
      this.lock();
    }

    lock() {
      this.piece.forEach(([c, r]) => {
        const y = this.py + r;
        const x = this.px + c;
        if (y >= 0 && y < ROWS && x >= 0 && x < COLS) {
          this.board[y][x] = KEYS.indexOf(this.pieceKey) + 1;
        }
      });
      this.clearLines();
      if (!this.over) this.spawn();
    }

    clearLines() {
      const kept = this.board.filter((row) => row.some((v) => v === 0));
      const cleared = ROWS - kept.length;
      if (!cleared) return;

      const empty = Array.from({ length: cleared }, () => new Array(COLS).fill(0));
      this.board = [...empty, ...kept];
      this.lines += cleared;
      this.score += SCORE_PER_LINE * (LINE_BONUS[cleared] || cleared);
      this.fallInterval = Math.max(MIN_FALL, BASE_FALL - this.lines * 12);
      if (this.onScoreChange) this.onScoreChange();
    }

    ghostY() {
      let gy = this.py;
      while (!this.collide(this.piece, this.px, gy + 1)) gy += 1;
      return gy;
    }

    togglePause() {
      if (this.over) return;
      this.paused = !this.paused;
      if (this.onPauseChange) this.onPauseChange(this.paused);
    }

    onSwipe(dir) {
      if (this.over || this.paused) return;
      if (dir === 'left') this.move(-1);
      else if (dir === 'right') this.move(1);
      else if (dir === 'up') this.rotate();
      else if (dir === 'down') this.hardDrop();
    }

    bindKeys() {
      Game.keys.clear();
      Game.keys.init();

      Game.keys.on('arrowleft', () => this.move(-1));
      Game.keys.on('a', () => this.move(-1));
      Game.keys.on('arrowright', () => this.move(1));
      Game.keys.on('d', () => this.move(1));
      Game.keys.on('arrowup', () => this.rotate());
      Game.keys.on('w', () => this.rotate());
      Game.keys.on('arrowdown', () => this.step());
      Game.keys.on('s', () => this.step());
      Game.keys.on(' ', () => this.hardDrop());
    }

    update(dt) {
      if (!this.over && !this.paused) {
        this.acc += dt;
        while (this.acc >= this.fallInterval) {
          this.acc -= this.fallInterval;
          this.step();
          if (this.over) break;
        }
      }
      this.draw();
    }

    draw() {
      const ctx = this.ctx;
      const s = this.cell;

      ctx.fillStyle = Game.COLORS.bg;
      ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

      ctx.save();
      ctx.translate(this.offsetX, 0);

      Game.draw.grid(ctx, COLS, ROWS, s, Game.COLORS.grid);

      // 已固定方块
      for (let r = 0; r < ROWS; r++) {
        for (let c = 0; c < COLS; c++) {
          const v = this.board[r][c];
          if (v) {
            Game.draw.cell(ctx, c, r, s, Game.COLORS.blocks[(v - 1) % Game.COLORS.blocks.length]);
          }
        }
      }

      if (!this.over) {
        // 落点预览
        const gy = this.ghostY();
        this.piece.forEach(([c, r]) => {
          if (gy + r >= 0) Game.draw.cell(ctx, this.px + c, gy + r, s, Game.COLORS.panel);
        });

        // 当前方块
        this.piece.forEach(([c, r]) => {
          if (this.py + r >= 0) Game.draw.cell(ctx, this.px + c, this.py + r, s, this.color);
        });
      }

      ctx.restore();
    }
  }

  window.TetrisGame = TetrisGame;
})();
