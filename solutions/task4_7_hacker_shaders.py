"""
Задача 4.7 (уровень сложности: хакер)
======================================
Расширенная система для работы с пиксельными шейдерами в Питоне.

Улучшения по сравнению с базовой версией из практического занятия:
  1. Переменная t — полная поддержка анимации (каждый шейдер принимает t).
  2. Параллельный рендеринг — модуль multiprocessing (Pool по числу ядер CPU);
     для сравнения доступен последовательный режим.
  3. Расширенный интерфейс на Tkinter+ttk:
       • выпадающий список для выбора шейдера,
       • кнопки Pause/Resume и Reset t,
       • слайдер скорости анимации,
       • переключатель Parallel / Sequential,
       • строка состояния: t, FPS, время кадра, режим рендеринга.

Включены шейдеры для всех задач блока 4 (4.1-4.6) в анимированном виде,
а также плазменный эффект в качестве дополнительного бонуса.

Запуск:
    python task4_7_hacker_shaders.py
"""

import math
import time
import tkinter as tk
from tkinter import ttk
from multiprocessing import Pool, cpu_count

# ── Параметры по умолчанию ────────────────────────────────────────────────────
WIDTH  = 256
HEIGHT = 256
SCALE  = 2          # масштаб отображения (реальный размер окна = 512×512)
TARGET_FPS = 30


# ══════════════════════════════════════════════════════════════════════════════
#  Вспомогательные функции шума (без random, без глобального состояния)
# ══════════════════════════════════════════════════════════════════════════════

def noise(x, y):
    """Хэш-шум: псевдослучайное значение в [0, 1) по целым координатам (x, y).

    Использует дробную часть sinа — стандартный трюк шейдерного программирования.
    """
    n = math.sin(x * 127.1 + y * 311.7) * 43758.5453123
    return n - math.floor(n)


def val_noise(x, y):
    """Value noise: билинейная интерполяция noise() по сетке целых узлов.

    Smoothstep-сглаживание (3t²-2t³) убирает «блочность» на стыках.
    """
    ix = math.floor(x)
    iy = math.floor(y)
    fx = x - ix
    fy = y - iy

    # Smoothstep: более плавный переход, чем линейная интерполяция
    ux = fx * fx * (3.0 - 2.0 * fx)
    uy = fy * fy * (3.0 - 2.0 * fy)

    a = noise(ix,     iy)
    b = noise(ix + 1, iy)
    c = noise(ix,     iy + 1)
    d = noise(ix + 1, iy + 1)

    # Билинейная интерполяция
    ab = a + (b - a) * ux
    cd = c + (d - c) * ux
    return ab + (cd - ab) * uy


def fbm(x, y, octaves=6):
    """Фрактальный шум (fBm) из нескольких октав val_noise.

    На каждой октаве амплитуда уменьшается вдвое, а частота удваивается.
    Результат находится в [0, 1).
    """
    value     = 0.0
    amplitude = 0.5
    frequency = 1.0
    for _ in range(octaves):
        value     += amplitude * val_noise(x * frequency, y * frequency)
        amplitude *= 0.5
        frequency *= 2.0
    return value


# ══════════════════════════════════════════════════════════════════════════════
#  Шейдеры (signature: func(x, y, t) → (r, g, b), все значения в [0, 1])
#
#  x, y ∈ [0, 1) — нормализованные экранные координаты
#  t    ∈ [0, ∞) — время анимации в секундах (условных единицах)
# ══════════════════════════════════════════════════════════════════════════════

# ── 4.1: Чёрный квадрат (анимированный) ──────────────────────────────────────
def shader_black_square(x, y, t=0.0):
    """«Чёрный квадрат» Малевича — покачивается на белом фоне."""
    # Квадрат пульсирует в размере
    margin = 0.15 + 0.03 * math.sin(t * 2.0)
    inside = margin < x < 1.0 - margin and margin < y < 1.0 - margin
    v = 0.0 if inside else 1.0
    return v, v, v


# ── 4.2: Шар ─────────────────────────────────────────────────────────────────
def shader_sphere(x, y, t=0.0):
    """Шар с псевдодиффузным освещением. Источник света вращается вокруг шара."""
    cx, cy = 0.5, 0.5
    r      = 0.42
    dx, dy = x - cx, y - cy
    dist2  = dx * dx + dy * dy
    if dist2 >= r * r:
        return 0.0, 0.0, 0.0
    # Нормаль на поверхности сферы
    dz = math.sqrt(r * r - dist2)
    nx, ny, nz = dx / r, dy / r, dz / r
    # Вращающийся источник света
    lx = math.cos(t)
    ly = math.sin(t) * 0.6
    lz = math.sqrt(max(0.0, 1.0 - lx * lx - ly * ly))
    diff = max(0.0, nx * lx + ny * ly + nz * lz)
    # Цвет: жёлто-зелёный, как на изображении из задания
    return diff, diff * 0.85, 0.0


# ── 4.3: Пак-Ман ──────────────────────────────────────────────────────────────
def shader_pacman(x, y, t=0.0):
    """Пак-Ман с анимированным ртом и движением по экрану."""
    # Персонаж движется вправо и «телепортируется» с края
    offset_x = (t * 0.15) % 1.2 - 0.1
    px = x - 0.5 - offset_x
    py = y - 0.5

    r    = 0.35
    dist = math.sqrt(px * px + py * py)

    # Угол рта пульсирует
    mouth = 0.28 + 0.22 * abs(math.sin(t * 5.0))
    angle = math.atan2(py, px)

    # Тело
    in_body = (dist < r) and not (abs(angle) < mouth and px > 0)
    # Глаз
    in_eye  = math.sqrt((px - 0.09) ** 2 + (py + 0.14) ** 2) < 0.055

    if in_eye:
        return 0.0, 0.0, 0.0
    if in_body:
        return 1.0, 0.9, 0.0
    return 0.0, 0.0, 0.0


# ── 4.4: Белый шум ────────────────────────────────────────────────────────────
def shader_white_noise(x, y, t=0.0):
    """Белый шум. Обновляется каждый кадр через сдвиг семени по t."""
    # Разные значения t дают разные «кадры» шума
    seed = math.floor(t * TARGET_FPS)
    v    = noise(x * WIDTH + seed * 1234.567, y * HEIGHT + seed * 9876.543)
    return v, v, v


# ── 4.5: Value noise ──────────────────────────────────────────────────────────
def shader_val_noise(x, y, t=0.0):
    """Value noise с плавным смещением по времени."""
    v = val_noise(x * 8.0 + t * 0.4, y * 8.0 + t * 0.3)
    return v, v, v


# ── 4.6: Облака (fBm) ─────────────────────────────────────────────────────────
def shader_clouds(x, y, t=0.0):
    """Анимированные облака на основе фрактального шума (fBm)."""
    v = fbm(x * 4.0 + t * 0.18, y * 4.0 + t * 0.12)
    v = max(0.0, min(1.0, v))
    # Смешиваем небесно-голубой с белым
    r = 0.38 + 0.62 * v
    g = 0.62 + 0.38 * v
    b = 0.92 + 0.08 * v
    return r, g, b


# ── Бонус: плазменный эффект ─────────────────────────────────────────────────
def shader_plasma(x, y, t=0.0):
    """Классический плазменный эффект — четыре интерферирующих синусоиды."""
    v  = math.sin(x * 10.0 + t * 2.0)
    v += math.sin(y * 10.0 + t * 1.5)
    v += math.sin((x + y) * 8.0 + t * 1.2)
    cx = x - 0.5 + 0.3 * math.sin(t * 0.7)
    cy = y - 0.5 + 0.3 * math.cos(t * 0.5)
    v += math.sin(math.sqrt(cx * cx + cy * cy) * 14.0 + t * 2.5)
    v = (v + 4.0) / 8.0  # нормализация в [0, 1]
    r = (math.sin(v * math.pi * 2.0)          + 1.0) / 2.0
    g = (math.sin(v * math.pi * 2.0 + 2.094) + 1.0) / 2.0
    b = (math.sin(v * math.pi * 2.0 + 4.189) + 1.0) / 2.0
    return r, g, b


# ── Реестр: порядок определяет нумерацию в выпадающем списке ─────────────────
SHADERS = [
    shader_black_square,   # 4.1
    shader_sphere,         # 4.2
    shader_pacman,         # 4.3
    shader_white_noise,    # 4.4
    shader_val_noise,      # 4.5
    shader_clouds,         # 4.6
    shader_plasma,         # бонус
]

SHADER_LABELS = [
    "4.1 Чёрный квадрат",
    "4.2 Шар",
    "4.3 Пак-Ман",
    "4.4 Белый шум",
    "4.5 Value noise",
    "4.6 Облака (fBm)",
    "Бонус: плазма",
]


# ══════════════════════════════════════════════════════════════════════════════
#  Рендеринг
# ══════════════════════════════════════════════════════════════════════════════

def _render_row(args):
    """Отрисовка одной строки пикселей (вызывается в рабочем процессе)."""
    y, width, height, t, shader_idx = args
    shader = SHADERS[shader_idx]
    row    = bytearray(width * 3)
    inv_w  = 1.0 / width
    inv_h  = 1.0 / height
    for x in range(width):
        r, g, b = shader(x * inv_w, y * inv_h, t)
        row[x * 3]     = max(0, min(255, int(r * 255)))
        row[x * 3 + 1] = max(0, min(255, int(g * 255)))
        row[x * 3 + 2] = max(0, min(255, int(b * 255)))
    return y, bytes(row)


def render_parallel(shader_idx, width, height, t, pool):
    """Рендеринг кадра параллельно — по одному процессу на строку."""
    args  = [(y, width, height, t, shader_idx) for y in range(height)]
    image = bytearray(3 * width * height)
    for y, row in pool.map(_render_row, args):
        image[y * width * 3:(y + 1) * width * 3] = row
    header = bytes(f'P6\n{width} {height}\n255\n', 'ascii')
    return header + bytes(image)


def render_sequential(shader_idx, width, height, t):
    """Рендеринг кадра последовательно (для сравнения производительности)."""
    image  = bytearray(3 * width * height)
    shader = SHADERS[shader_idx]
    inv_w  = 1.0 / width
    inv_h  = 1.0 / height
    for y in range(height):
        base = y * width * 3
        for x in range(width):
            r, g, b = shader(x * inv_w, y * inv_h, t)
            pos = base + x * 3
            image[pos]     = max(0, min(255, int(r * 255)))
            image[pos + 1] = max(0, min(255, int(g * 255)))
            image[pos + 2] = max(0, min(255, int(b * 255)))
    header = bytes(f'P6\n{width} {height}\n255\n', 'ascii')
    return header + bytes(image)


# ══════════════════════════════════════════════════════════════════════════════
#  Интерфейс (Tkinter + ttk)
# ══════════════════════════════════════════════════════════════════════════════

class ShaderApp:
    """Главное приложение: анимированный просмотр шейдеров с управлением."""

    FRAME_MS = 1000 // TARGET_FPS  # целевой интервал между кадрами

    def __init__(self, width=WIDTH, height=HEIGHT, scale=SCALE):
        self.width      = width
        self.height     = height
        self.scale      = scale
        self.t          = 0.0
        self.dt         = 1.0 / TARGET_FPS
        self.paused     = False
        self.parallel   = True
        self.shader_idx = 0
        self._pool      = None
        self._img_ref   = None  # удерживаем ссылку — иначе PhotoImage будет уничтожен GC

    # ── Запуск ────────────────────────────────────────────────────────────────

    def run(self):
        self._pool = Pool(processes=cpu_count())

        root = tk.Tk()
        root.title("Pixel Shader Viewer — Hacker Edition (задача 4.7)")
        root.resizable(False, False)
        self._root = root

        self._build_ui()
        root.after(0, self._frame)
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        root.mainloop()

    # ── Построение интерфейса ─────────────────────────────────────────────────

    def _build_ui(self):
        root = self._root

        # Холст для изображения
        self._canvas = tk.Label(root, bd=0, bg="black")
        self._canvas.pack()

        # ── Панель управления ─────────────────────────────────────────────────
        ctrl = tk.Frame(root, pady=6, padx=8)
        ctrl.pack(fill=tk.X)

        # Выбор шейдера
        tk.Label(ctrl, text="Шейдер:").grid(row=0, column=0, sticky="w")
        self._shader_var = tk.StringVar(value=SHADER_LABELS[self.shader_idx])
        cb = ttk.Combobox(
            ctrl, textvariable=self._shader_var,
            values=SHADER_LABELS, state="readonly", width=22,
        )
        cb.grid(row=0, column=1, padx=(4, 12), sticky="w")
        cb.bind("<<ComboboxSelected>>", self._on_shader_change)

        # Play / Pause
        self._play_btn = tk.Button(
            ctrl, text="⏸  Pause", width=10, command=self._toggle_pause,
        )
        self._play_btn.grid(row=0, column=2, padx=4)

        # Сброс t
        tk.Button(ctrl, text="⏮  Reset t", width=10,
                  command=self._reset_t).grid(row=0, column=3, padx=4)

        # Скорость анимации
        tk.Label(ctrl, text="Speed:").grid(row=0, column=4, padx=(12, 0))
        self._speed_var = tk.DoubleVar(value=1.0)
        tk.Scale(
            ctrl, variable=self._speed_var,
            from_=0.1, to=5.0, resolution=0.1,
            orient=tk.HORIZONTAL, length=100, showvalue=True,
        ).grid(row=0, column=5, padx=4)

        # Параллельный / последовательный режим
        self._par_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            ctrl, text=f"Parallel ({cpu_count()} cores)",
            variable=self._par_var,
            command=self._on_parallel_change,
        ).grid(row=0, column=6, padx=(12, 0))

        # ── Строка состояния ──────────────────────────────────────────────────
        self._status_var = tk.StringVar(value="Инициализация…")
        status_bar = tk.Label(
            root, textvariable=self._status_var,
            relief=tk.SUNKEN, anchor="w",
            font=("Courier", 9), pady=2, padx=6,
        )
        status_bar.pack(fill=tk.X)

    # ── Цикл кадров ───────────────────────────────────────────────────────────

    def _frame(self):
        t0 = time.perf_counter()

        if self.parallel and self._pool is not None:
            data = render_parallel(
                self.shader_idx, self.width, self.height, self.t, self._pool,
            )
        else:
            data = render_sequential(
                self.shader_idx, self.width, self.height, self.t,
            )

        img = tk.PhotoImage(data=data).zoom(self.scale, self.scale)
        self._canvas.config(image=img)
        self._img_ref = img  # защита от GC

        elapsed = time.perf_counter() - t0
        fps     = 1.0 / elapsed if elapsed > 0.0 else 0.0
        mode    = f"parallel×{cpu_count()}" if self.parallel else "sequential"
        self._status_var.set(
            f"t = {self.t:7.3f}   "
            f"FPS = {fps:5.1f}   "
            f"{elapsed * 1000:5.1f} ms/frame   "
            f"[{mode}]"
        )

        if not self.paused:
            self.t += self.dt * self._speed_var.get()

        # Следующий кадр: ждём оставшееся время до целевого интервала
        delay = max(1, self.FRAME_MS - int(elapsed * 1000))
        self._root.after(delay, self._frame)

    # ── Обработчики событий ───────────────────────────────────────────────────

    def _on_shader_change(self, _event=None):
        label = self._shader_var.get()
        self.shader_idx = SHADER_LABELS.index(label)
        self.t = 0.0

    def _toggle_pause(self):
        self.paused = not self.paused
        self._play_btn.config(text="▶  Play" if self.paused else "⏸  Pause")

    def _reset_t(self):
        self.t = 0.0

    def _on_parallel_change(self):
        self.parallel = self._par_var.get()

    def _on_close(self):
        if self._pool is not None:
            self._pool.terminate()
            self._pool.join()
        self._root.destroy()


# ══════════════════════════════════════════════════════════════════════════════
#  Точка входа
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Защита обязательна для multiprocessing на Windows/macOS (на Linux не нужна,
    # но является хорошей практикой).
    app = ShaderApp(width=WIDTH, height=HEIGHT, scale=SCALE)
    app.run()
