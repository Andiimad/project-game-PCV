import glob
import math
import os
import random
import sys
import time
from collections import deque
import cv2
import numpy as np

WIN = "Magic Touch Inspired Game"
FONT = cv2.FONT_HERSHEY_SIMPLEX
NUM_POINTS = 4
ON_FRAMES = 2            
OFF_RATIO = 0.5          
WRONG_PENALTY = 1.5      
START_LIVES = 3
KILLS_PER_WAVE = 3
DEBOUNCE = 0.8          
SOUND = True

SPRITE_SCALE = 0.6      
KEY_OUT_WHITE = True     
WHITE_THRESHOLD = 235    


PATTERNS = [
    ("Zigzag",    [0, 1, 2, 3]),
    ("Segitiga",  [0, 1, 2, 0]),
    ("Huruf U",   [0, 2, 3, 1]),
    ("Kotak",     [0, 1, 3, 2, 0]),
    ("Huruf N",   [2, 0, 3, 1]),
    ("Jam Pasir", [0, 3, 2, 1, 0]),
]
ENEMY_COLORS = [(200, 120, 60), (90, 200, 90), (80, 80, 230), (200, 90, 200), (60, 180, 230)]

GREEN, RED, CYAN, YELLOW, WHITE, GRAY = (0, 255, 0), (0, 0, 255), (255, 255, 0), \
    (0, 255, 255), (255, 255, 255), (160, 160, 160)


def nothing(_):
    pass

# ---------- Deteksi warna & titik ----------
def color_mask(img, h_center, h_tol, s_min, v_min):
    blur = cv2.GaussianBlur(img, (7, 7), 0)
    hsv = cv2.cvtColor(blur, cv2.COLOR_BGR2HSV)
    lo, hi = h_center - h_tol, h_center + h_tol
    ranges = []
    if lo < 0:
        ranges += [(0, hi), (180 + lo, 179)]
    elif hi > 179:
        ranges += [(lo, 179), (0, hi - 180)]
    else:
        ranges.append((lo, hi))
    mask = np.zeros(hsv.shape[:2], np.uint8)
    for a, b in ranges:
        mask |= cv2.inRange(hsv, np.array([a, s_min, v_min], np.uint8),
                            np.array([b, 255, 255], np.uint8))
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k, iterations=1)
    return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k, iterations=2)


def zone_ratio(mask, cx, cy, r):
    h, w = mask.shape
    x0, y0 = max(0, cx - r), max(0, cy - r)
    x1, y1 = min(w, cx + r + 1), min(h, cy + r + 1)
    if x1 <= x0 or y1 <= y0:
        return 0.0
    sub = mask[y0:y1, x0:x1]
    circ = np.zeros(sub.shape, np.uint8)
    cv2.circle(circ, (cx - x0, cy - y0), r, 255, -1)
    total = cv2.countNonZero(circ)
    return cv2.countNonZero(cv2.bitwise_and(sub, circ)) / total if total else 0.0


def update_states(states, ratios, thr):
    newly = []
    for i, (st, ratio) in enumerate(zip(states, ratios)):
        if not st["active"]:
            st["streak"] = st["streak"] + 1 if ratio >= thr else 0
            if st["streak"] >= ON_FRAMES:
                st["active"] = True
                newly.append(i)
        elif ratio < thr * OFF_RATIO:
            st["active"], st["streak"] = False, 0
    return newly


def find_yellow(mask, min_area=400):
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None
    c = max(cnts, key=cv2.contourArea)
    if cv2.contourArea(c) < min_area:
        return None
    m = cv2.moments(c)
    if m["m00"] == 0:
        return None
    return (int(m["m10"] / m["m00"]), int(m["m01"] / m["m00"]))


class PointsState:
    def __init__(self):
        self.pos = None
        self.drag = -1
        self.radius = 35
        self.size = (640, 480)


def default_positions(w, h):
    return [(int(w * 0.2), int(h * 0.42)), (int(w * 0.8), int(h * 0.42)),
            (int(w * 0.2), int(h * 0.84)), (int(w * 0.8), int(h * 0.84))]


def on_mouse(event, x, y, flags, st):
    if st.pos is None:
        return
    if event == cv2.EVENT_LBUTTONDOWN:
        for i, (px, py) in enumerate(st.pos):
            if (x - px) ** 2 + (y - py) ** 2 <= (st.radius + 12) ** 2:
                st.drag = i
                break
    elif event == cv2.EVENT_MOUSEMOVE and st.drag >= 0:
        w, h = st.size
        st.pos[st.drag] = (int(np.clip(x, 0, w - 1)), int(np.clip(y, 0, h - 1)))
    elif event == cv2.EVENT_LBUTTONUP:
        st.drag = -1

# ---------- Logika game ----------
class Enemy:
    def __init__(self, name, seq, now, limit, color, sprite=None):
        self.name, self.seq, self.color = name, seq, color
        self.sprite = sprite                  
        self.progress = 0
        self.limit = limit
        self.deadline = now + limit
        self.last_idx, self.last_time = -1, 0.0

    def remaining(self, now):
        return max(0.0, self.deadline - now)

class Game:
    def __init__(self):
        self.sprite_count = 0
        self.reset()

    def reset(self):
        self.state = "ready"            
        self.score, self.lives, self.wave, self.kills = 0, START_LIVES, 1, 0
        self.enemy = None
        self.msg = None               
        self.fx = None                 
        self.hurt_until = 0.0

    def start(self, now):
        self.reset()
        self.state = "playing"
        self.spawn(now)

    def time_limit(self):
        return max(5.0, 12.0 - 0.8 * (self.wave - 1))

    def spawn(self, now):
        pool = PATTERNS[:min(len(PATTERNS), 2 + self.wave)]
        prev = self.enemy.name if self.enemy else None
        choices = [p for p in pool if p[0] != prev] or pool
        name, seq = random.choice(choices)
        sprite = None
        if self.sprite_count:
            prev_sprite = self.enemy.sprite if self.enemy else None
            options = [i for i in range(self.sprite_count) if i != prev_sprite] or [0]
            sprite = random.choice(options)
        self.enemy = Enemy(name, list(seq), now, self.time_limit(),
                           random.choice(ENEMY_COLORS), sprite)

    def flash(self, text, color, now, dur=1.0):
        self.msg = (text, color, now + dur)

    def on_touch(self, idx, now):
        """Dipanggil saat sebuah titik BARU tersentuh. Mengembalikan nama event atau None."""
        e = self.enemy
        if self.state != "playing" or e is None:
            return None
        if idx == e.last_idx and now - e.last_time < DEBOUNCE:
            return None                              # kedipan sentuhan yang sama
        if idx == e.seq[e.progress]:
            e.progress += 1
            e.last_idx, e.last_time = idx, now
            if e.progress == len(e.seq):
                return self._kill(now)
            return "ok"
        e.progress = 1 if idx == e.seq[0] else 0     # boleh langsung mulai ulang dari titik awal
        e.last_idx, e.last_time = idx, now
        e.deadline -= WRONG_PENALTY
        self.flash(f"SALAH! -{WRONG_PENALTY:g} detik", RED, now, 0.9)
        return "wrong"

    def _kill(self, now):
        e = self.enemy
        gain = 100 + int(e.remaining(now) * 10)
        self.score += gain
        self.kills += 1
        self.fx = (now, e.color)
        self.flash(f"{e.name.upper()} KALAH!  +{gain}", GREEN, now, 1.2)
        if self.kills % KILLS_PER_WAVE == 0:
            self.wave += 1
        self.spawn(now)
        return "kill"

    def tick(self, now):
        e = self.enemy
        if self.state != "playing" or e is None or now < e.deadline:
            return None
        self.lives -= 1
        self.hurt_until = now + 0.3
        if self.lives <= 0:
            self.state, self.enemy = "gameover", None
            return "dead"
        self.flash("MUSUH MENYERANG!  -1 nyawa", RED, now, 1.2)
        self.spawn(now)
        return "hurt"

# ---------- Gambar ----------
def put(img, text, org, scale=0.7, color=WHITE, thick=2):
    cv2.putText(img, text, org, FONT, scale, (0, 0, 0), thick + 3, cv2.LINE_AA)
    cv2.putText(img, text, org, FONT, scale, color, thick, cv2.LINE_AA)


def put_center(img, text, y, scale=0.7, color=WHITE, thick=2, cx=None):
    (tw, _), _ = cv2.getTextSize(text, FONT, scale, thick)
    cx = img.shape[1] // 2 if cx is None else cx
    put(img, text, (int(cx - tw / 2), int(y)), scale, color, thick)


def draw_dashed(img, p, q, color, thick=2, dash=14):
    dist = math.hypot(q[0] - p[0], q[1] - p[1])
    n = max(1, int(dist // dash))
    for i in range(0, n, 2):
        a = (int(p[0] + (q[0] - p[0]) * i / n), int(p[1] + (q[1] - p[1]) * i / n))
        b = (int(p[0] + (q[0] - p[0]) * min(i + 1, n) / n),
             int(p[1] + (q[1] - p[1]) * min(i + 1, n) / n))
        cv2.line(img, a, b, color, thick, cv2.LINE_AA)


def draw_arrow(img, a, b, color, thick):
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    dx, dy = b[0] - a[0], b[1] - a[1]
    d = math.hypot(dx, dy) or 1.0
    ux, uy = dx / d, dy / d
    p = (int(mx - ux * 8), int(my - uy * 8))
    q = (int(mx + ux * 8), int(my + uy * 8))
    cv2.arrowedLine(img, p, q, color, thick, cv2.LINE_AA, tipLength=0.9)


def draw_heart(img, cx, cy, s, color):
    cv2.circle(img, (cx - s // 2, cy - s // 4), s // 2, color, -1)
    cv2.circle(img, (cx + s // 2, cy - s // 4), s // 2, color, -1)
    tri = np.array([[cx - s, cy - s // 8], [cx + s, cy - s // 8], [cx, cy + s]], np.int32)
    cv2.fillPoly(img, [tri], color)

class SpriteBank:

    def __init__(self, folder):
        self.images, self.names, self.cache = [], [], {}
        paths = [os.path.join(folder, "enemy.png")]
        for ext in ("png", "webp"):
            paths += sorted(glob.glob(os.path.join(folder, "enemies", "*." + ext)))
        for p in paths:
            if not os.path.isfile(p):
                continue
            img = self._load(p)
            if img is None:
                print(f"[sprite] gagal memuat: {p}")
                continue
            self.images.append(img)
            self.names.append(os.path.relpath(p, folder))

    @staticmethod
    def _load(path):
        try:
            data = np.fromfile(path, np.uint8)          
            img = cv2.imdecode(data, cv2.IMREAD_UNCHANGED)
        except Exception:
            return None
        if img is None or img.size == 0:
            return None
        if img.dtype == np.uint16:
            img = (img / 257).astype(np.uint8)
        elif img.dtype != np.uint8:
            img = np.clip(img, 0, 255).astype(np.uint8)
        if img.ndim == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
        elif img.shape[2] == 3:                         # tanpa alpha
            alpha = np.full(img.shape[:2], 255, np.uint8)
            if KEY_OUT_WHITE:
                white = np.all(img >= WHITE_THRESHOLD, axis=2)
                alpha[white] = 0
                alpha = cv2.GaussianBlur(alpha, (3, 3), 0)
            img = np.dstack([img, alpha])
        return img

    def __len__(self):
        return len(self.images)

    def get(self, idx, height):

        height = max(16, int(height))
        key = (idx, height)
        if key not in self.cache:
            img = self.images[idx]
            scale = height / img.shape[0]
            size = (max(1, int(round(img.shape[1] * scale))), height)
            interp = cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR
            self.cache[key] = cv2.resize(img, size, interpolation=interp)
        return self.cache[key]


def overlay_rgba(dst, sprite, cx, cy, tint=0.0):
    sh, sw = sprite.shape[:2]
    x0, y0 = int(cx - sw / 2), int(cy - sh / 2)
    X0, Y0 = max(0, x0), max(0, y0)
    X1, Y1 = min(dst.shape[1], x0 + sw), min(dst.shape[0], y0 + sh)
    if X1 <= X0 or Y1 <= Y0:
        return
    sp = sprite[Y0 - y0:Y1 - y0, X0 - x0:X1 - x0]
    rgb = sp[:, :, :3].astype(np.float32)
    if tint > 0:                                      
        rgb = rgb * (1 - tint) + np.array([0, 0, 255], np.float32) * tint
    a = sp[:, :, 3:4].astype(np.float32) / 255.0
    roi = dst[Y0:Y1, X0:X1].astype(np.float32)
    dst[Y0:Y1, X0:X1] = (a * rgb + (1 - a) * roi).astype(np.uint8)


def draw_panel(view, lines):
    h, w = view.shape[:2]
    ph = len(lines) * 36 + 30
    x0, x1 = int(w * .1), int(w * .9)
    y0 = h // 2 - ph // 2
    sub = view[y0:y0 + ph, x0:x1]
    view[y0:y0 + ph, x0:x1] = cv2.addWeighted(sub, 0.35, np.zeros_like(sub), 0.65, 0)
    for i, (text, scale, color) in enumerate(lines):
        put_center(view, text, y0 + 40 + i * 36, scale, color)


def step_label(seq, i):
    return ",".join(str(k + 1) for k, s in enumerate(seq) if s == i)


def render(frame, game, pos, states, ratios, radius, now, trail, cur, show_ratio, sprites=None):
    h, w = frame.shape[:2]
    overlay = frame.copy()
    for (x, y), st in zip(pos, states):
        if st["active"]:
            cv2.circle(overlay, (x, y), radius, GREEN, -1)
    view = cv2.addWeighted(overlay, 0.4, frame, 0.6, 0)

    # trail
    tl = list(trail)
    for i in range(1, len(tl)):
        if tl[i - 1] is not None and tl[i] is not None:
            f = i / len(tl)
            cv2.line(view, tl[i - 1], tl[i], (0, int(255 * f), int(255 * f)),
                     int(1 + 6 * f), cv2.LINE_AA)
    if cur is not None:
        cv2.circle(view, cur, 9, (0, 0, 0), -1, cv2.LINE_AA)
        cv2.circle(view, cur, 6, YELLOW, -1, cv2.LINE_AA)

    e = game.enemy
    xs, ys = [p[0] for p in pos], [p[1] for p in pos]
    center = (sum(xs) / 4, sum(ys) / 4)
    size = max(30, int(0.22 * min(max(xs) - min(xs), max(ys) - min(ys))))

    if e is not None:
        low = e.remaining(now) < 0.3 * e.limit
        if sprites is not None and e.sprite is not None and e.sprite < len(sprites):
            spread = min(max(xs) - min(xs), max(ys) - min(ys))
            sp = sprites.get(e.sprite, SPRITE_SCALE * spread)
            dx = 3 * math.sin(now * 40) if low else 0      
            dy = 6 * math.sin(now * 3)                     
            overlay_rgba(view, sp, center[0] + dx, center[1] + dy, tint=0.3 if low else 0.0)
        for k in range(len(e.seq) - 1):                    
            a, b = pos[e.seq[k]], pos[e.seq[k + 1]]
            if e.progress >= k + 2:
                cv2.line(view, a, b, GREEN, 6, cv2.LINE_AA)
            elif e.progress == k + 1:
                draw_dashed(view, a, b, CYAN, 4)
                draw_arrow(view, a, b, CYAN, 4)
            else:
                draw_dashed(view, a, b, (230, 230, 230), 2)
                draw_arrow(view, a, b, (230, 230, 230), 2)

    if game.fx is not None and now - game.fx[0] < 0.6:        
        p = (now - game.fx[0]) / 0.6
        cv2.circle(view, (int(center[0]), int(center[1])), int(size * (1 + 3 * p)),
                   game.fx[1], max(1, int(10 * (1 - p))), cv2.LINE_AA)

    # titik + nomor urutan
    nxt = e.seq[e.progress] if (e is not None and e.progress < len(e.seq)) else -1
    for i, ((x, y), st, ratio) in enumerate(zip(pos, states, ratios)):
        col = GREEN if st["active"] else GRAY
        cv2.circle(view, (x, y), radius, col, 3 if st["active"] else 2, cv2.LINE_AA)
        if i == nxt:
            cv2.circle(view, (x, y), int(radius + 7 + 4 * math.sin(now * 6)), CYAN, 3, cv2.LINE_AA)
        if e is not None:
            steps = [k for k, s in enumerate(e.seq) if s == i]
            if steps:
                lc = GREEN if all(k < e.progress for k in steps) else (CYAN if i == nxt else WHITE)
                put_center(view, step_label(e.seq, i), y - radius - 14, 0.8, lc, 2, cx=x)
        if show_ratio:
            put_center(view, f"{int(ratio * 100)}%", y + radius + 22, 0.5, col, 1, cx=x)

    # HUD
    put(view, f"SKOR {game.score}", (15, 32), 0.8, YELLOW)
    put(view, f"WAVE {game.wave}", (15, 60), 0.6, WHITE)
    for i in range(START_LIVES):
        draw_heart(view, w - 30 - i * 38, 26, 10, RED if i < game.lives else (90, 90, 90))
    if e is not None:
        put_center(view, f"GAMBAR: {e.name.upper()}", 40, 0.8, WHITE)
        frac = float(np.clip(e.remaining(now) / e.limit, 0, 1))
        cv2.rectangle(view, (15, 74), (w - 15, 90), (40, 40, 40), -1)
        bar_col = (0, int(255 * min(1, frac * 2)), int(255 * min(1, (1 - frac) * 2 + 0.2)))
        cv2.rectangle(view, (15, 74), (15 + int((w - 30) * frac), 90), bar_col, -1)
        cv2.rectangle(view, (15, 74), (w - 15, 90), WHITE, 1)

    if game.msg is not None and now < game.msg[2]:
        put_center(view, game.msg[0], h // 2 + 8, 1.0, game.msg[1], 3)
    if now < game.hurt_until:
        view = cv2.addWeighted(view, 0.7, np.full_like(view, (0, 0, 255)), 0.3, 0)

    if game.state == "ready":
        draw_panel(view, [("Game Project PCV", 1.1, YELLOW),
                          ("Gambar pola musuh dengan objek KUNING", 0.6, WHITE),
                          ("sentuh titik sesuai urutan angka", 0.6, WHITE),
                          ("Atur titik & slider, lalu tekan SPASI", 0.6, CYAN)])
    elif game.state == "gameover":
        draw_panel(view, [("GAME OVER", 1.2, RED),
                          (f"Skor: {game.score}   Wave: {game.wave}", 0.8, WHITE),
                          ("Tekan SPASI untuk main lagi", 0.6, CYAN)])

    put(view, "Drag titik: pindah | SPASI: mulai | r: reset titik | m: mask | q: keluar",
        (15, h - 12), 0.45, WHITE, 1)
    return view

# ---------- Main ----------
def main():
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    if not cap.isOpened():
        raise RuntimeError("Kamera tidak bisa dibuka")

    pts = PointsState()
    cv2.namedWindow(WIN)
    cv2.setMouseCallback(WIN, on_mouse, pts)
    cv2.namedWindow("Controls")
    cv2.createTrackbar("H center", "Controls", 30, 179, nothing)
    cv2.createTrackbar("H tol", "Controls", 10, 30, nothing)
    cv2.createTrackbar("S min", "Controls", 100, 255, nothing)
    cv2.createTrackbar("V min", "Controls", 100, 255, nothing)
    cv2.createTrackbar("Radius", "Controls", 35, 100, nothing)
    cv2.createTrackbar("Hit %", "Controls", 25, 100, nothing)

    states = [{"active": False, "streak": 0} for _ in range(NUM_POINTS)]
    game = Game()
    sprites = SpriteBank(os.path.dirname(os.path.abspath(__file__)))
    game.sprite_count = len(sprites)
    trail = deque(maxlen=30)
    show_mask = True

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frame = cv2.flip(frame, 1)
        h, w = frame.shape[:2]
        pts.size = (w, h)
        if pts.pos is None:
            pts.pos = default_positions(w, h)

        radius = max(8, cv2.getTrackbarPos("Radius", "Controls"))
        thr = max(0.02, cv2.getTrackbarPos("Hit %", "Controls") / 100.0)
        pts.radius = radius

        mask = color_mask(frame, cv2.getTrackbarPos("H center", "Controls"),
                          cv2.getTrackbarPos("H tol", "Controls"),
                          cv2.getTrackbarPos("S min", "Controls"),
                          cv2.getTrackbarPos("V min", "Controls"))
        ratios = [zone_ratio(mask, x, y, radius) for x, y in pts.pos]
        newly = update_states(states, ratios, thr)
        cur = find_yellow(mask)
        trail.append(cur)

        now = time.time()
        if game.state == "playing":
            for i in newly:
                ev = game.on_touch(i, now)
            ev = game.tick(now)

        view = render(frame, game, pts.pos, states, ratios, radius, now, trail, cur,
                      show_ratio=(game.state != "playing"), sprites=sprites)
        cv2.imshow(WIN, view)
        if show_mask:
            mview = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
            for (x, y), st in zip(pts.pos, states):
                cv2.circle(mview, (x, y), radius, GREEN if st["active"] else RED, 2)
            cv2.imshow("Mask", mview)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        elif key == ord(" ") and game.state in ("ready", "gameover"):
            game.start(time.time())
            trail.clear()
        elif key == ord("m"):
            show_mask = not show_mask
            if not show_mask:
                cv2.destroyWindow("Mask")
        elif key == ord("r"):
            pts.pos = default_positions(w, h)

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()