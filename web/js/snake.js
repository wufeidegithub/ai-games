/* ============================================================
   贪吃蛇 —— 网页版
   与 Python 版逻辑一致，便于对照
   ============================================================ */

(function () {
  const COLS = 20;
  const ROWS = 20;
  const INIT_LENGTH = 4;
  const SCORE_PER_FOOD = 10;
  const SPEEDUP_EVERY = 50;
  const BASE_INTERVAL = 140;   // 毫秒/格
  const MIN_INTERVAL = 60;

  class SnakeGame {
    constructor(canvas) {
      this.canvas = canvas;
      this.ctx = canvas.getContext('2d');
      this.cell = canvas.width / COLS;

      // 由 app.js 注入的回调
      this.onScoreChange = null;
      this.onGameOver = null;
      this.onPauseChange = null;

      this.reset();
    }

    reset() {
      const cx = Math.floor(COLS / 2);
      const cy = Math.floor(ROWS / 2);

      this.snake = Array.from({ length: INIT_LENGTH }, (_, i) => [cx - i, cy]);
      this.dir = [1, 0];
      this.pending = [1, 0];
      this.score = 0;
      this.paused = false;
      this.over = false;
      this.acc = 0;
      this.interval = BASE_INTERVAL;
      this.food = this.randomFood();

      this.bindKeys();
      if (this.onScoreChange) this.onScoreChange();
      this.draw();
    }

    randomFood() {
      const taken = new Set(this.snake.map(([c, r]) => `${c},${r}`));
      const free = [];
      for (let c = 0; c < COLS; c++) {
        for (let r = 0; r < ROWS; r++) {
          if (!taken.has(`${c},${r}`)) free.push([c, r]);
        }
      }
      return free.length ? free[Game.randInt(free.length)] : null;
    }

    bindKeys() {
      Game.keys.clear();
      Game.keys.init();

      const set = (dir) => {
        if (this.over || this.paused) return;
        const [dx, dy] = dir;
        // 不允许 180 度掉头
        if (dx !== -this.dir[0] || dy !== -this.dir[1]) {
          this.pending = dir;
        }
      };

      Game.keys.on('arrowup', () => set([0, -1]));
      Game.keys.on('w', () => set([0, -1]));
      Game.keys.on('arrowdown', () => set([0, 1]));
      Game.keys.on('s', () => set([0, 1]));
      Game.keys.on('arrowleft', () => set([-1, 0]));
      Game.keys.on('a', () => set([-1, 0]));
      Game.keys.on('arrowright', () => set([1, 0]));
      Game.keys.on('d', () => set([1, 0]));
      Game.keys.on(' ', () => this.togglePause());
    }

    /** 手机端滑动 */
    onSwipe(dir) {
      if (this.over || this.paused) return;
      const map = { up: [0, -1], down: [0, 1], left: [-1, 0], right: [1, 0] };
      const d = map[dir];
      if (!d) return;
      if (d[0] !== -this.dir[0] || d[1] !== -this.dir[1]) this.pending = d;
    }

    togglePause() {
      if (this.over) return;
      this.paused = !this.paused;
      if (this.onPauseChange) this.onPauseChange(this.paused);
    }

    update(dt) {
      if (this.over || this.paused) {
        this.draw();
        return;
      }

      this.acc += dt;
      while (this.acc >= this.interval) {
        this.acc -= this.interval;
        this.step();
        if (this.over) break;
      }
      this.draw();
    }

    step() {
      this.dir = this.pending;

      const [hx, hy] = this.snake[0];
      const nx = hx + this.dir[0];
      const ny = hy + this.dir[1];

      // 撞墙
      if (nx < 0 || nx >= COLS || ny < 0 || ny >= ROWS) {
        return this.gameOver();
      }

      // 咬到自己（尾巴本帧会移开，排除最后一节）
      const body = this.snake.slice(0, -1);
      if (body.some(([c, r]) => c === nx && r === ny)) {
        return this.gameOver();
      }

      this.snake.unshift([nx, ny]);

      if (this.food && nx === this.food[0] && ny === this.food[1]) {
        this.score += SCORE_PER_FOOD;
        this.food = this.randomFood();
        const level = Math.floor(this.score / SPEEDUP_EVERY);
        this.interval = Math.max(MIN_INTERVAL, BASE_INTERVAL - level * 10);
        if (this.onScoreChange) this.onScoreChange();
      } else {
        this.snake.pop();
      }
    }

    gameOver() {
      this.over = true;
      if (this.onGameOver) this.onGameOver(this.score);
    }

    draw() {
      const ctx = this.ctx;
      const s = this.cell;

      ctx.fillStyle = Game.COLORS.bg;
      ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

      Game.draw.grid(ctx, COLS, ROWS, s, Game.COLORS.grid);

      if (this.food) {
        Game.draw.cell(ctx, this.food[0], this.food[1], s, Game.COLORS.danger, 4, 5);
      }

      this.snake.forEach(([c, r], i) => {
        const color = i === 0 ? Game.COLORS.accent : Game.COLORS.snakeBody;
        Game.draw.cell(ctx, c, r, s, color);
      });
    }
  }

  window.SnakeGame = SnakeGame;
})();
