import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

import pymupdf

ROTATE = 90  # 右に90度
ROTATE_ONLY_LANDSCAPE = True  # True: 横長ページのPDFだけ回転 (縦長のファイルは t で切替)

# 枠はA4縦の比率 (幅:高さ = 1:√2) に固定。回転"後"の見た目基準で
# (高さ = ページ高さに対する割合, 縦位置 0=上寄せ 0.5=中央 1=下寄せ)。横は中央。
A4_RATIO = 2 ** 0.5
PRESETS = {
    "A": (0.90, 0.0),  # 上寄せ (下余白をカット)
    "B": (0.90, 1.0),  # 下寄せ (上余白をカット)
    "C": (0.90, 0.5),  # 中央
}
DEFAULT_ODD, DEFAULT_EVEN = "A", "B"  # ページ番号は1始まり
WHEEL_ZOOM = 1.1  # ホイール1目盛りの表示倍率
VIEW_MARGIN = 280  # 画面の高さからこれを引いた分をプレビューの高さにする(px)。見切れるなら増やす
OUT_DIR = Path(__file__).resolve().parent / "out"


def open_rotated(path, rotate):
    doc = pymupdf.open(path)
    for page in doc:
        page.set_rotation((page.rotation + rotate) % 360)
    return doc


def initial_rotate(path):
    if not ROTATE_ONLY_LANDSCAPE:
        return ROTATE
    with pymupdf.open(path) as doc:
        return ROTATE if doc[0].rect.width > doc[0].rect.height else 0


def a4_frame(rect, h, cx, cy):
    """高さ割合h・中心(cx, cy)のA4比率の枠を、ページ内に収めて割合で返す。"""
    h = min(h, 1.0, rect.width * A4_RATIO / rect.height)  # ページ幅を超えない
    w = h * rect.height / A4_RATIO / rect.width
    x0 = max(0.0, min(1 - w, cx - w / 2))
    y0 = max(0.0, min(1 - h, cy - h / 2))
    return (x0, y0, x0 + w, y0 + h)


def preset_frame(name, rect):
    h, v = PRESETS[name]
    return a4_frame(rect, h, 0.5, h / 2 + v * (1 - h))


def default_frame(i, rect):
    return preset_frame(DEFAULT_ODD if i % 2 == 0 else DEFAULT_EVEN, rect)


class App:
    def __init__(self, root, files):
        self.root = root
        self.view_h = root.winfo_screenheight() - VIEW_MARGIN
        self.out_dir = OUT_DIR
        self.rel = files  # path -> 表示・出力用の相対パス
        self.files = list(files)
        self.state = {}  # path -> (rotate, frames)  ファイルを行き来しても設定を保持
        self.saved = set()
        self.drag = None

        side = tk.Frame(root)
        side.pack(side="left", fill="y")
        tk.Label(side, text="✓保存済  ●表示済", anchor="w").pack(fill="x")
        self.listbox = tk.Listbox(side, width=34, takefocus=0, exportselection=False, font=("Helvetica", 13))
        self.listbox.pack(fill="y", expand=True)
        self.listbox.bind("<<ListboxSelect>>", self.on_list)

        self.title = tk.Label(root, anchor="w", font=("Helvetica", 18, "bold"))
        self.title.pack(fill="x")
        self.info = tk.Label(root, anchor="w", font=("Helvetica", 13))
        self.info.pack(fill="x")
        bar = tk.Frame(root)
        bar.pack(side="bottom", fill="x")

        # 右: 枠サイズのスライダー (ページ高さに対する割合)
        self.size_var = tk.DoubleVar()
        tk.Label(root, text="枠サイズ").pack(side="right", anchor="n")
        self.slider = tk.Scale(root, from_=1.0, to=0.3, resolution=0.01, variable=self.size_var,
                               orient="vertical", length=self.view_h - 100, takefocus=0, command=self.on_size)
        self.slider.pack(side="right", fill="y")

        # 中央: プレビュー (ホイールで拡大縮小、はみ出たらスクロールバー)
        self.view_zoom = 1.0
        area = tk.Frame(root)
        area.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(area, bg="#666", highlightthickness=0,
                                width=int(self.view_h / A4_RATIO), height=self.view_h)
        ys = tk.Scrollbar(area, orient="vertical", command=self.canvas.yview)
        xs = tk.Scrollbar(area, orient="horizontal", command=self.canvas.xview)
        self.canvas.config(yscrollcommand=ys.set, xscrollcommand=xs.set)
        ys.pack(side="right", fill="y")
        xs.pack(side="bottom", fill="x")
        self.canvas.pack(fill="both", expand=True)
        tk.Button(bar, text="◀◀ 前ファイル", command=lambda: self.go_file(-1)).pack(side="left")
        tk.Button(bar, text="◀", command=lambda: self.go(-1)).pack(side="left")
        tk.Button(bar, text="▶", command=lambda: self.go(1)).pack(side="left")
        tk.Button(bar, text="次ファイル ▶▶", command=lambda: self.go_file(1)).pack(side="left")
        tk.Button(bar, text="回転切替 (t)", command=self.toggle_rotate).pack(side="left")
        for k, name in enumerate(PRESETS, 1):
            tk.Button(bar, text=f"{k}: {name}", command=lambda n=name: self.set_preset(n)).pack(side="left")
        tk.Button(bar, text="同じ奇偶へコピー (a)", command=self.copy_parity).pack(side="left")
        tk.Button(bar, text="保存 (s)", command=self.save).pack(side="right")

        root.bind("<Left>", lambda e: self.go(-1))
        root.bind("<Right>", lambda e: self.go(1))
        for k, name in enumerate(PRESETS, 1):
            root.bind(str(k), lambda e, n=name: self.set_preset(n))
        root.bind("a", lambda e: self.copy_parity())
        root.bind("r", lambda e: self.reset())
        root.bind("s", lambda e: self.save())
        root.bind("n", lambda e: self.go_file(1))
        root.bind("p", lambda e: self.go_file(-1))
        root.bind("t", lambda e: self.toggle_rotate())
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_move)
        for b in ("<ButtonPress-2>", "<ButtonPress-3>"):  # macOSは2、他は3が右クリック
            self.canvas.bind(b, self.on_rpress)
        for b in ("<B2-Motion>", "<B3-Motion>"):
            self.canvas.bind(b, self.on_rmove)
        for b in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.canvas.bind(b, self.on_wheel)
        self.load(0)

    # --- ファイル ---
    def load(self, fidx, last_page=False):
        self.fidx = fidx
        self.path = self.files[fidx]
        if self.path not in self.state:
            self.state[self.path] = [initial_rotate(self.path), None]
        self.rotate = self.state[self.path][0]
        self.doc = open_rotated(self.path, self.rotate)
        if self.state[self.path][1] is None:  # 回転後のページ寸法で枠を作る
            self.state[self.path][1] = [default_frame(i, p.rect) for i, p in enumerate(self.doc)]
        self.frames = self.state[self.path][1]
        self.idx = len(self.doc) - 1 if last_page else 0
        self.render()

    def go_file(self, d, last_page=False):
        if 0 <= self.fidx + d < len(self.files):
            self.load(self.fidx + d, last_page)

    def refresh_list(self):
        self.listbox.delete(0, "end")
        for i, p in enumerate(self.files):
            m = "✓" if p in self.saved else "●" if p in self.state else "  "
            self.listbox.insert("end", f"{m} {self.rel[p]}")
            if p in self.saved:
                self.listbox.itemconfig(i, fg="#2a8a2a")
        self.listbox.selection_set(self.fidx)
        self.listbox.see(self.fidx)

    def on_list(self, e):
        sel = self.listbox.curselection()
        if sel and sel[0] != self.fidx:
            self.load(sel[0])
        self.root.focus_set()

    def toggle_rotate(self):
        self.state[self.path] = [0 if self.rotate else ROTATE, None]  # 寸法が変わるので枠は作り直し
        self.load(self.fidx)

    # --- 表示 ---
    def render(self):
        page = self.doc[self.idx]
        zoom = self.view_h * self.view_zoom / page.rect.height
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
        self.img = tk.PhotoImage(data=pix.tobytes("ppm"))
        self.w, self.h = pix.width, pix.height
        self.canvas.config(scrollregion=(0, 0, self.w, self.h))
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, image=self.img, anchor="nw")
        self.draw_frame()

    def draw_frame(self):
        self.canvas.delete("frame")
        x0, y0, x1, y1 = self.frames[self.idx]
        X0, Y0, X1, Y1 = x0 * self.w, y0 * self.h, x1 * self.w, y1 * self.h
        shade = dict(fill="black", stipple="gray50", outline="", tags="frame")
        self.canvas.create_rectangle(0, 0, self.w, Y0, **shade)
        self.canvas.create_rectangle(0, Y1, self.w, self.h, **shade)
        self.canvas.create_rectangle(0, Y0, X0, Y1, **shade)
        self.canvas.create_rectangle(X1, Y0, self.w, Y1, **shade)
        self.canvas.create_rectangle(X0, Y0, X1, Y1, outline="red", width=2, tags="frame")
        rect = self.doc[self.idx].rect
        name = next((n for n in PRESETS if preset_frame(n, rect) == self.frames[self.idx]), "カスタム")
        parity = "奇数" if self.idx % 2 == 0 else "偶数"
        self.size_var.set(round(y1 - y0, 2))  # variable経由ならcommandは呼ばれない
        self.refresh_list()
        mark = "  ✓保存済" if self.path in self.saved else ""
        self.title.config(text=f"  [{self.fidx + 1}/{len(self.files)}] {self.rel[self.path]}{mark}")
        self.info.config(text=f"  p.{self.idx + 1}/{len(self.doc)} ({parity})   枠: {name}   回転: {self.rotate}°")

    # --- 操作 ---
    def go(self, d):
        i = self.idx + d
        if i < 0:
            return self.go_file(-1, last_page=True)
        if i >= len(self.doc):
            return self.go_file(1)
        self.idx = i
        self.render()

    def set_preset(self, name):
        self.frames[self.idx] = preset_frame(name, self.doc[self.idx].rect)
        self.draw_frame()

    def reset(self):
        self.frames[self.idx] = default_frame(self.idx, self.doc[self.idx].rect)
        self.draw_frame()

    def on_size(self, value):
        x0, y0, x1, y1 = self.frames[self.idx]
        h = float(value)
        if abs(h - (y1 - y0)) < 0.005:
            return
        v = y0 / (1 - (y1 - y0)) if y1 - y0 < 1 else 0.5  # 縦位置(上寄せ/下寄せ)を保つ
        self.frames[self.idx] = a4_frame(self.doc[self.idx].rect, h, (x0 + x1) / 2, h / 2 + v * (1 - h))
        self.draw_frame()

    def on_wheel(self, e):
        up = e.delta > 0 or e.num == 4
        self.view_zoom = max(0.5, min(4.0, self.view_zoom * (WHEEL_ZOOM if up else 1 / WHEEL_ZOOM)))
        self.render()

    def copy_parity(self):
        f = self.frames[self.idx]
        for i in range(self.idx % 2, len(self.frames), 2):
            self.frames[i] = f
        self.draw_frame()

    def on_press(self, e):
        self.drag = (self.canvas.canvasx(e.x), self.canvas.canvasy(e.y), self.frames[self.idx])

    def on_move(self, e):
        if not self.drag:
            return
        sx, sy, (x0, y0, x1, y1) = self.drag
        dx = (self.canvas.canvasx(e.x) - sx) / self.w
        dy = (self.canvas.canvasy(e.y) - sy) / self.h
        dx = max(-x0, min(1 - x1, dx))  # ページ外にはみ出さない
        dy = max(-y0, min(1 - y1, dy))
        self.frames[self.idx] = (x0 + dx, y0 + dy, x1 + dx, y1 + dy)
        self.draw_frame()

    def on_rpress(self, e):
        self.rstart = (self.canvas.canvasx(e.x), self.canvas.canvasy(e.y))

    def on_rmove(self, e):
        # 縦方向のドラッグ量で高さを決め、幅はA4比率から自動
        sy, ey = sorted((self.rstart[1] / self.h, self.canvas.canvasy(e.y) / self.h))
        if ey - sy > 0.05:
            self.frames[self.idx] = a4_frame(self.doc[self.idx].rect, ey - sy, self.rstart[0] / self.w, (sy + ey) / 2)
            self.draw_frame()

    # --- 保存 ---
    def save(self):
        out = self.out_dir / self.rel[self.path]
        out.parent.mkdir(parents=True, exist_ok=True)
        doc = open_rotated(self.path, self.rotate)  # 毎回元ファイルから作り直す
        for page, (x0, y0, x1, y1) in zip(doc, self.frames):
            r = page.rect  # 回転後の座標系
            view = pymupdf.Rect(r.x0 + x0 * r.width, r.y0 + y0 * r.height,
                                r.x0 + x1 * r.width, r.y0 + y1 * r.height)
            box = view * page.derotation_matrix  # 回転前の座標系へ
            box.normalize()
            cb = page.cropbox
            page.set_cropbox((box + (cb.x0, cb.y0, cb.x0, cb.y0)) & cb)
        doc.save(out, garbage=1)  # 画像・ベクターは再エンコードしない
        doc.close()
        self.saved.add(self.path)
        if self.fidx + 1 < len(self.files):
            self.go_file(1)
        else:
            self.draw_frame()
            messagebox.showinfo("保存", f"最後のファイルを保存しました:\n{self.out_dir}")


def collect(args):
    """引数(フォルダ/PDF)から {絶対パス: 相対パス} を作る。"""
    files = {}
    for a in args:
        p = Path(a).expanduser().resolve()
        if p.is_dir():
            for f in sorted(p.rglob("*.pdf")):
                if not f.name.startswith("."):
                    files.setdefault(f, f.relative_to(p))
        elif p.suffix.lower() == ".pdf" and p.is_file():
            files.setdefault(p, Path(p.name))
        else:
            print(f"スキップ: {a}", file=sys.stderr)
    return files


def main():
    root = tk.Tk()
    root.title("Score Trim")
    args = sys.argv[1:] or [filedialog.askdirectory()]
    if not args[0]:
        return
    files = collect(args)
    if not files:
        messagebox.showerror("エラー", f"PDFがありません: {' '.join(args)}")
        return
    App(root, files)
    root.mainloop()


if __name__ == "__main__":
    main()
