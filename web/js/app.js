/* ============================================================
   应用路由：大厅 <-> 游戏页
   ============================================================ */

(function () {
  const lobby = document.getElementById('lobby');
  const play = document.getElementById('play');
  const canvas = document.getElementById('canvas');
  const overlay = document.getElementById('overlay');
  const overlayText = document.getElementById('overlay-text');
  const overlayHint = document.getElementById('overlay-hint');
  const hudTitle = document.getElementById('hud-title');
  const scoreEl = document.getElementById('score');
  const bestEl = document.getElementById('best');
  const controlsEl = document.getElementById('controls');
  const btnBack = document.getElementById('btn-back');
  const btnPause = document.getElementById('btn-pause');

  // 各游戏的元信息与控制器
  const REGISTRY = {
    snake: {
      title: '贪吃蛇',
      controls: '方向键 / WASD 移动 · 空格暂停 · R 重开',
      create: () => new window.SnakeGame(canvas),
    },
    tetris: {
      title: '俄罗斯方块',
      controls: '← → 移动 · ↑ 旋转 · ↓ 加速 · 空格直落 · P 暂停',
      create: () => new window.TetrisGame(canvas),
    },
  };

  let current = null;   // 当前游戏实例
  let currentKey = null;
  let stopLoop = null;

  /** 刷新大厅里的最高分 */
  function refreshBest() {
    document.querySelectorAll('[data-best]').forEach((el) => {
      el.textContent = Game.best.get(el.dataset.best);
    });
  }

  /** 更新游戏页 HUD */
  function syncHud() {
    if (!current) return;
    scoreEl.textContent = current.score;
    bestEl.textContent = Math.max(Game.best.get(currentKey), current.score);
  }

  function showOverlay(text, hint) {
    overlayText.textContent = text;
    overlayHint.textContent = hint;
    overlay.classList.remove('hidden');
  }

  function hideOverlay() {
    overlay.classList.add('hidden');
  }

  function startGame(key) {
    const meta = REGISTRY[key];
    if (!meta) return;

    currentKey = key;
    current = meta.create();

    hudTitle.textContent = meta.title;
    controlsEl.textContent = meta.controls;
    btnPause.textContent = '暂停';

    // 游戏自己要用的回调
    current.onScoreChange = syncHud;
    current.onGameOver = (score) => {
      const isRecord = Game.best.set(key, score);
      syncHud();
      showOverlay('游戏结束', isRecord ? '新纪录！按 R 重开' : '按 R 重开');
    };
    current.onPauseChange = (paused) => {
      btnPause.textContent = paused ? '继续' : '暂停';
      if (paused) showOverlay('已暂停', '按 P 或点「继续」');
      else hideOverlay();
    };

    hideOverlay();
    syncHud();

    lobby.classList.remove('active');
    play.classList.add('active');

    current.reset();
    if (stopLoop) stopLoop();
    stopLoop = Game.loop.start((dt) => current.update(dt));
  }

  function exitGame() {
    if (stopLoop) {
      stopLoop();
      stopLoop = null;
    }
    current = null;
    currentKey = null;
    Game.keys.clear();
    Game.keys.init();

    play.classList.remove('active');
    lobby.classList.add('active');
    refreshBest();
  }

  // ---------- 事件绑定 ----------

  document.querySelectorAll('.game-card').forEach((card) => {
    card.addEventListener('click', () => startGame(card.dataset.game));
  });

  btnBack.addEventListener('click', exitGame);

  btnPause.addEventListener('click', () => {
    if (current) current.togglePause();
  });

  // 全局按键：Esc 返回，R 重开
  window.addEventListener('keydown', (e) => {
    if (!current) return;
    const k = e.key.toLowerCase();
    if (k === 'escape') {
      exitGame();
    } else if (k === 'r') {
      current.reset();
      hideOverlay();
    } else if (k === 'p') {
      current.togglePause();
    }
  });

  // 离开页面时停掉循环，省电
  document.addEventListener('visibilitychange', () => {
    if (document.hidden && current && !current.paused) {
      current.togglePause();
    }
  });

  // 触屏滑动支持（手机端）
  let touchStart = null;
  canvas.addEventListener('touchstart', (e) => {
    const t = e.touches[0];
    touchStart = { x: t.clientX, y: t.clientY };
  }, { passive: true });

  canvas.addEventListener('touchend', (e) => {
    if (!touchStart || !current || !current.onSwipe) return;
    const t = e.changedTouches[0];
    const dx = t.clientX - touchStart.x;
    const dy = t.clientY - touchStart.y;
    if (Math.abs(dx) < 24 && Math.abs(dy) < 24) return; // 视为点击

    if (Math.abs(dx) > Math.abs(dy)) {
      current.onSwipe(dx > 0 ? 'right' : 'left');
    } else {
      current.onSwipe(dy > 0 ? 'down' : 'up');
    }
    touchStart = null;
  }, { passive: true });

  Game.keys.init();
  refreshBest();
})();
