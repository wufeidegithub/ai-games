/* ============================================================
   公共工具：本地存储、键盘、游戏循环、绘制辅助
   ============================================================ */

const Game = {};

/** 最高分读写（localStorage，按游戏名隔离） */
Game.best = {
  key: (name) => `ai-games:best:${name}`,
  get(name) {
    return Number(localStorage.getItem(this.key(name)) || 0);
  },
  set(name, score) {
    const cur = this.get(name);
    if (score > cur) {
      localStorage.setItem(this.key(name), String(score));
      return true;
    }
    return false;
  },
};

/** 键盘状态：按下集合 + 一次性触发回调 */
Game.keys = {
  down: new Set(),
  handlers: new Map(),

  init() {
    window.addEventListener('keydown', (e) => {
      const k = e.key.toLowerCase();
      // 方向键和空格会滚动页面，拦掉
      if (['arrowup', 'arrowdown', 'arrowleft', 'arrowright', ' '].includes(k)) {
        e.preventDefault();
      }
      if (!this.down.has(k)) {
        this.down.add(k);
        const fn = this.handlers.get(k);
        if (fn) fn();
      }
    });

    window.addEventListener('keyup', (e) => {
      this.down.delete(e.key.toLowerCase());
    });
  },

  /** 注册一次性按键回调（keydown 时触发一次，不重复） */
  on(key, fn) {
    this.handlers.set(key.toLowerCase(), fn);
  },

  clear() {
    this.down.clear();
    this.handlers.clear();
  },
};

/** 变长游戏循环：回调收到经过的毫秒数 */
Game.loop = {
  start(onFrame) {
    let last = performance.now();
    let raf = null;
    const tick = (now) => {
      const dt = Math.min(now - last, 100); // 切标签页回来时避免大跳
      last = now;
      onFrame(dt);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  },
};

/** 画布绘制辅助 */
Game.draw = {
  /** 带圆角的方格 */
  cell(ctx, col, row, size, color, inset = 1, radius = 3) {
    const x = col * size + inset;
    const y = row * size + inset;
    const s = size - inset * 2;
    ctx.fillStyle = color;
    if (ctx.roundRect) {
      ctx.beginPath();
      ctx.roundRect(x, y, s, s, radius);
      ctx.fill();
    } else {
      ctx.fillRect(x, y, s, s);
    }
  },

  /** 网格线 */
  grid(ctx, cols, rows, size, color) {
    ctx.strokeStyle = color;
    ctx.lineWidth = 1;
    for (let c = 0; c <= cols; c++) {
      const x = c * size + 0.5;
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, rows * size);
      ctx.stroke();
    }
    for (let r = 0; r <= rows; r++) {
      const y = r * size + 0.5;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(cols * size, y);
      ctx.stroke();
    }
  },
};

/** 调色板，节奏与 Python 版一致 */
Game.COLORS = {
  bg: '#181a20',
  panel: '#22252d',
  grid: '#2c303a',
  accent: '#56b6ff',
  danger: '#ff5c5c',
  snakeBody: '#5696dc',
  blocks: ['#56b6ff', '#7ed957', '#ffc759', '#ff8a65', '#ba8cff', '#ff799e', '#5ee0ca'],
};

/** 随机整数 [0, n) */
Game.randInt = (n) => Math.floor(Math.random() * n);

/** 简单防抖，用于 resize 之类 */
Game.debounce = (fn, ms = 100) => {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  };
};
