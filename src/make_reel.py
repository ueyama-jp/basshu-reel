#!/usr/bin/env python3
"""BasShu リール動画メーカー(4テンプレート / 素材3枚 / 12秒)

テンプレート: slide(スライド型) / zoom(ゆっくりズーム型) /
              detail(ディテール型) / notice(告知型)

使い方:
    python3 make_reel.py 設定.json 出力.mp4

設定.json の例は sample_config.json を参照。
動きは「ゆっくりしたズーム」と「クロスフェード」だけ。凝った演出は入れない。
"""
import json
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

W, H, FPS = 1080, 1920, 30
TOTAL_SECONDS = 12   # 動画全体の長さ(秒)。写真3枚で等分する

# 色(文字は白、地と下地はグレー)
WHITE = (255, 255, 255)      # 動画の文字の色
GRAY = (108, 108, 108)       # 告知の画面(文字が主役の画面)の地
PLATE = (72, 72, 72)         # 写真に重ねる文字の下地(半透明のグレー)
PLATE_ALPHA = 175            # 下地の濃さ(0〜255)

# 書体(サイトと同じゴシック体)。明朝体にしたいときは、SERIF の行を NotoSerifCJK-Regular.ttc に変える
SANS = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
SERIF = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"  # 見出し(ひとこと、商品名)


def font(path, size):
    return ImageFont.truetype(path, size, index=0)  # index 0 = 日本語(JP)


def ease(t):
    """ゆっくり始まり、ゆっくり終わる"""
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


# 文字を置く高さ。Instagramのリール画面で、下のアカウント名やキャプションに隠れない位置
TEXT_Y = 1300
PANEL_TOP = 1150   # 最後の画面で、商品名のまとまりが始まる高さ
# 物撮り(白い背景の商品写真)は切らずに小さめに置き、地を白にして、文字を写真の上下に置く
# 写真の大きさ(幅)、写真の上端、上の文字の中心、下の文字の上端
STUDIO = dict(PW=900, PY=400, TOP_Y=300, BOT_Y=1340)
STUDIO_INK = (51, 51, 51)        # 物撮りの画面の文字の色
STUDIO_SUB = (112, 112, 112)     # 物撮りの画面の小さな文字の色
LABEL_Y = 270      # 「イメージ画像」の札の高さ(上の画面部品に隠れない位置)


def cover(img, zoom, h=None):
    """画像を枠(幅W×高さh)いっぱいに切り出す。zoom=1.0 でちょうど、1.06 で少し寄る"""
    h = h or H
    iw, ih = img.size
    scale = max(W / iw, h / ih) * zoom
    cw, ch = W / scale, h / scale
    left, top = (iw - cw) / 2, (ih - ch) / 2
    return img.resize((W, h), Image.LANCZOS, box=(left, top, left + cw, top + ch))


def spaced(draw, xy, text, fnt, fill, spacing=0, anchor_center=True):
    """字間をあけて文字を描く"""
    widths = [draw.textlength(c, font=fnt) for c in text]
    total = sum(widths) + spacing * (len(text) - 1)
    x, y = xy
    if anchor_center:
        x -= total / 2
    for c, w in zip(text, widths):
        draw.text((x, y), c, font=fnt, fill=fill)
        x += w + spacing
    return total


def fit_font(draw, text, path, size, max_width, spacing=0):
    """枠に収まるまで文字を小さくする"""
    while size > 24:
        f = font(path, size)
        width = sum(draw.textlength(c, font=f) for c in text) + spacing * (len(text) - 1)
        if width <= max_width:
            return f
        size -= 2
    return font(path, size)


VIDEO_EXT = (".mp4", ".mov", ".m4v", ".webm")


class Clip:
    """動画素材を1コマずつ読む(縦長に切り出し、音は使わない)"""

    def __init__(self, path):
        vf = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS}"
        self.proc = subprocess.Popen(
            ["ffmpeg", "-loglevel", "error", "-i", path, "-an", "-vf", vf,
             "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
        self.last = None

    def next(self):
        buf = self.proc.stdout.read(W * H * 3)
        if len(buf) == W * H * 3:
            self.last = Image.frombytes("RGB", (W, H), buf)
        if self.last is None:
            sys.exit("動画素材を読めませんでした")
        return self.last  # 素材が短いときは最後のコマで止める


def load(scene, cfg):
    if scene.get("card"):
        return card(cfg)
    path = scene["image"]
    if path.lower().endswith(VIDEO_EXT):
        return Clip(path)
    return ImageOps.exif_transpose(Image.open(path)).convert("RGB")


def plate(layer, y0, y1, strength):
    """文字のうしろに敷く、半透明のグレーの四角い下地(角は丸めず、ふちもぼかさない)"""
    sheet = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sheet).rectangle([56, y0, W - 56, y1], fill=PLATE + (strength,))
    return Image.alpha_composite(layer, sheet)


def text_style(layer, base, y0, y1, matted=False):
    """文字は白。写真に重なるときは半透明のグレーの下地を敷く(y0〜y1 が文字の範囲)。
    写真の下のグレーの地に置くとき(matted)は、下地はいらない"""
    if not matted:
        layer = plate(layer, y0 - 64, y1 + 56, PLATE_ALPHA)
    return layer, WHITE + (255,), WHITE + (232,)


_LOGO = {}


def logo(cfg, height):
    """ロゴ(白、背景透明のPNG)を指定の高さで返す。ロゴがなければ None(ブランド名の文字で代用)"""
    path = cfg.get("logo")
    if not path:
        return None
    if path not in _LOGO:
        try:
            _LOGO[path] = Image.open(path).convert("RGBA")
        except OSError:
            _LOGO[path] = None
    src = _LOGO[path]
    if src is None:
        return None
    src = src.crop(src.getchannel("A").getbbox() or (0, 0, *src.size))   # 余白を切る
    w = max(1, round(src.width * height / src.height))
    return src.resize((w, height), Image.LANCZOS)


def brand_mark(layer, cfg, y, height, fill, font_size):
    """ブランド名を中央に置く。ロゴがあればロゴ、なければ字間をあけた文字"""
    lg = logo(cfg, height)
    if lg is not None:
        layer.alpha_composite(lg, dest=(round((W - lg.width) / 2), round(y)))
    else:
        spaced(ImageDraw.Draw(layer), (W / 2, y), cfg.get("brand", "BasShu"), font(SANS, font_size), fill, spacing=14)


def studio_bg(img):
    """写真の四辺がほぼ白で均一なら、物撮りとみなして、その地の色を返す(シーン画像なら None)"""
    im = img.convert("RGB")
    w, h = im.size
    b = max(2, round(min(w, h) * 0.03))           # 四辺の帯の太さ(3%)
    strips = [im.crop((0, 0, w, b)), im.crop((0, h - b, w, h)), im.crop((0, 0, b, h)), im.crop((w - b, 0, w, h))]
    px = []
    for st in strips:
        raw = st.resize((max(1, st.width // 4), max(1, st.height // 4))).tobytes()
        px += [tuple(raw[i:i + 3]) for i in range(0, len(raw), 3)]
    lum = [0.299 * r + 0.587 * g + 0.114 * bl for r, g, bl in px]
    mean = sum(lum) / len(lum)
    spread = (sum((x - mean) ** 2 for x in lum) / len(lum)) ** 0.5
    chroma = sum(max(p) - min(p) for p in px) / len(px)
    if mean >= 222 and spread <= 14 and chroma <= 16:   # 明るく、ばらつきが小さく、色みのない白
        n = len(px)
        return tuple(round(sum(p[i] for p in px) / n) for i in range(3))
    return None


def place(img, z, bg=None):
    """写真を画面に置く。物撮り(bg あり)は、その地の色の上に、小さめに切らずに置く。
    それ以外(シーン画像、動画、縦長)は画面いっぱいに置く"""
    if bg is None:
        return cover(img, z)
    canvas = Image.new("RGB", (W, H), bg)
    w = round(STUDIO["PW"] * z)
    h = round(w * img.height / img.width)
    cy = STUDIO["PY"] + STUDIO["PW"] * img.height / img.width / 2
    canvas.paste(img.convert("RGB").resize((w, h), Image.LANCZOS), (round((W - w) / 2), round(cy - h / 2)))
    return canvas


def tinted_logo(cfg, height, color):
    """白いロゴを、白い地でも見える色に塗り替える"""
    lg = logo(cfg, height)
    if lg is None:
        return None
    solid = Image.new("RGBA", lg.size, color + (255,))
    solid.putalpha(lg.getchannel("A"))
    return solid


def studio_overlay(scene, cfg):
    """物撮りの画面の文字。地が白いので下地は敷かず、濃い色の文字を写真の上と下に置く"""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    kind = scene.get("overlay")
    top, bot = STUDIO["TOP_Y"], STUDIO["BOT_Y"]
    ink, sub = STUDIO_INK + (255,), STUDIO_SUB + (255,)

    def mark():
        lg = tinted_logo(cfg, z(52), STUDIO_INK)
        if lg is not None:
            layer.alpha_composite(lg, dest=(round((W - lg.width) / 2), round(top - lg.height / 2)))
        else:
            spaced(d, (W / 2, top - z(16)), cfg.get("brand", "BasShu"), font(SANS, z(30)), sub, spacing=14)

    if kind == "copy":       # ひとことは写真の上、小さな2〜3行は写真の下
        f = fit_font(d, scene["text"], SERIF, z(68), W - 160, spacing=z(8))
        spaced(d, (W / 2, top - f.size * 0.62), scene["text"], f, ink, spacing=z(8))
        for i, line in enumerate(clean_lines(scene.get("lines"))):
            f = fit_font(d, line, SERIF, z(35), W - 200, spacing=z(4))
            spaced(d, (W / 2, bot + z(52) * i), line, f, sub, spacing=z(4))
    elif kind in ("caption", "panel"):   # ロゴは写真の上、商品名などは写真の下
        mark()
        f = fit_font(d, cfg["name"] if kind == "panel" else scene["text"], SERIF, z(58), W - 160, spacing=z(4))
        spaced(d, (W / 2, bot), cfg["name"] if kind == "panel" else scene["text"], f, ink, spacing=z(4))
        y = bot + z(80)
        if kind == "panel" and cfg.get("variant"):
            spaced(d, (W / 2, y), cfg["variant"], font(SANS, z(32)), sub, spacing=z(6))
            y += z(58)
        if kind == "panel" and cfg.get("price"):
            spaced(d, (W / 2, y), cfg["price"], font(SERIF, z(44)), ink, spacing=z(3))
            y += z(66)
        tag = cfg.get("tagline") if kind == "panel" else scene.get("sub")
        if tag:
            f = fit_font(d, tag, SERIF, z(34), W - 220, spacing=z(5))
            spaced(d, (W / 2, y), tag, f, sub, spacing=z(5))
    if scene.get("ai_label"):
        ai_label(d)
    return layer


def clean_lines(v):
    """小さく添える文章(2〜3行)を、行のリストにそろえる"""
    if isinstance(v, str):
        v = v.split("\n")
    return [str(x).strip() for x in (v or []) if str(x).strip()][:3]


def ai_label(d):
    """明るい写真でも読めるよう、小さな半透明の札に入れる"""
    f = font(SANS, 26)
    label = "イメージ画像"
    tw = d.textlength(label, font=f)
    x0, y0 = W - tw - 84, LABEL_Y
    d.rounded_rectangle([x0, y0, W - 40, y0 + 52], radius=26, fill=(30, 30, 30, 120))
    d.text((x0 + 22, y0 + 6), label, font=f, fill=(255, 255, 255, 240))


TS = 0.78   # 動画・写真に入る文字の大きさの倍率(1.0 が元の大きさ。小さくするほど控えめ)


def z(n):
    """大きさや間隔に、文字の倍率をかける"""
    return round(n * TS)


def overlay(scene, cfg, base=None, matted=False):
    """1場面に重ねる文字の層をつくる。base は文字が重なる写真(明るさを見るため)"""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    kind = scene.get("overlay")
    if kind == "copy":      # ひとこと + 小さく添える2〜3行
        lines = clean_lines(scene.get("lines"))
        top = TEXT_Y - z(44) * len(lines)       # 行が増えるぶん、全体を上へ
        bottom = top + z(100) + (z(36) + z(58) * len(lines) if lines else 0)
        layer, ink, sub = text_style(layer, base, top, bottom, matted)
        d = ImageDraw.Draw(layer)
        f = fit_font(d, scene["text"], SERIF, z(68), W - 200, spacing=z(8))
        spaced(d, (W / 2, top + z(14)), scene["text"], f, ink, spacing=z(8))
        for i, line in enumerate(lines):
            f = fit_font(d, line, SERIF, z(35), W - 220, spacing=z(4))
            spaced(d, (W / 2, top + z(132) + z(58) * i), line, f, sub, spacing=z(4))
    elif kind == "caption":  # 小さめの商品名
        bottom = TEXT_Y + z(124) + (z(70) if scene.get("sub") else 0)
        layer, ink, sub = text_style(layer, base, TEXT_Y, bottom, matted)
        brand_mark(layer, cfg, TEXT_Y - z(8), z(46), sub, z(28))
        d = ImageDraw.Draw(layer)
        f = fit_font(d, scene["text"], SERIF, z(50), W - 200, spacing=z(4))
        spaced(d, (W / 2, TEXT_Y + z(60)), scene["text"], f, ink, spacing=z(4))
        if scene.get("sub"):  # 商品名の下に添える、気の利いたひとこと
            f = fit_font(d, scene["sub"], SERIF, z(36), W - 240, spacing=z(5))
            spaced(d, (W / 2, TEXT_Y + z(146)), scene["sub"], f, sub, spacing=z(5))
    elif kind == "panel":    # 商品名・色・価格。写真は画面いっぱい、文字のうしろに半透明のグレーの下地
        top = PANEL_TOP
        y_end = top + z(244) + (z(72) if cfg.get("variant") else 0) + (z(92) if cfg.get("price") else 0) \
            + (z(64) if cfg.get("tagline") else 0)
        layer = plate(layer, top + z(6), y_end + z(34), PLATE_ALPHA)
        soft = WHITE + (228,)
        brand_mark(layer, cfg, top + z(44), z(52), soft, z(30))
        d = ImageDraw.Draw(layer)
        d.line([(W / 2 - z(36), top + z(114)), (W / 2 + z(36), top + z(114))], fill=soft, width=2)
        f = fit_font(d, cfg["name"], SERIF, z(58), W - 200, spacing=z(4))
        spaced(d, (W / 2, top + z(148)), cfg["name"], f, WHITE + (255,), spacing=z(4))
        y = top + z(244)
        if cfg.get("variant"):
            spaced(d, (W / 2, y), cfg["variant"], font(SANS, z(34)), soft, spacing=z(6))
            y += z(72)
        if cfg.get("price"):
            spaced(d, (W / 2, y), cfg["price"], font(SERIF, z(50)), WHITE + (255,), spacing=z(3))
            y += z(92)
        if cfg.get("tagline"):  # 価格の下に添えるひとこと
            f = fit_font(d, cfg["tagline"], SERIF, z(36), W - 240, spacing=z(5))
            spaced(d, (W / 2, y), cfg["tagline"], f, soft, spacing=z(5))
    if scene.get("ai_label"):
        ai_label(ImageDraw.Draw(layer))
    return layer


def card(cfg):
    """告知型の、文字が主役の画面"""
    img = Image.new("RGBA", (W, H), GRAY + (255,))
    lines = cfg.get("notice_lines", [])
    block = z(150) + z(110) + z(84) * len(lines)
    y = (H - block) / 2 - z(40)
    brand_mark(img, cfg, y - z(14), z(60), (232, 232, 232), z(32))
    d = ImageDraw.Draw(img)
    d.line([(W / 2 - z(36), y + z(70)), (W / 2 + z(36), y + z(70))], fill=(232, 232, 232), width=2)
    title = cfg.get("notice_title", "")
    f = fit_font(d, title, SERIF, z(84), W - 180, spacing=z(6))
    spaced(d, (W / 2, y + z(130)), title, f, WHITE, spacing=z(6))
    yy = y + z(290)
    for line in lines:
        f = fit_font(d, line, SANS, z(42), W - 200, spacing=z(3))
        spaced(d, (W / 2, yy), line, f, WHITE, spacing=z(3))
        yy += z(84)
    return img.convert("RGB")


def scenes_for(cfg):
    """テンプレートごとの3場面の中身。どれも最後は実物の商品写真で終わる"""
    t = cfg.get("template", "slide")
    ai = cfg.get("ai_image", True)
    whole = cfg["product_image"]
    close = cfg.get("detail_image") or whole          # 寄りの写真(なければ全体)
    extra = cfg.get("extra_image") or whole           # 別カットの写真(なければ全体)
    name = {"overlay": "caption", "text": cfg["name"], "sub": cfg.get("tagline")}
    if t in ("slide", "zoom"):
        last = {"overlay": "panel"} if t == "slide" else name
        # 2枚目には、素材やつくりの特徴のひとこと(あれば)を重ねる
        middle = {"image": close}
        if cfg.get("point"):
            middle.update(overlay="copy", text=cfg["point"], lines=cfg.get("point_lines"))
        return [{"image": cfg["wear_image"], "overlay": "copy", "text": cfg["copy"],
                 "lines": cfg.get("copy_lines"), "ai_label": ai},
                middle,
                dict(image=whole, **last)]
    if t == "detail":
        return [dict(image=whole, **name),
                {"image": close, "overlay": "copy", "text": cfg["copy"], "lines": cfg.get("copy_lines")},
                {"image": extra, "overlay": "panel"}]
    if t == "notice":
        return [{"card": True}, {"image": close}, dict(image=whole, **name)]
    sys.exit(f"知らないテンプレートです: {t}")


def with_alpha(layer, alpha):
    if alpha >= 1:
        return layer
    out = layer.copy()
    out.putalpha(out.getchannel("A").point(lambda v: int(v * alpha)))
    return out


def render(cfg, out_path):
    sc = scenes_for(cfg)
    hold = float(cfg.get("seconds_per_image", TOTAL_SECONDS / len(sc)))  # 1枚あたりの秒数
    fade = float(cfg.get("crossfade", 0.9))            # 切り替えにかける秒数(長いほどゆっくり)
    default_zoom = 0.10 if cfg.get("template") == "zoom" else 0.06
    zoom_amt = float(cfg.get("zoom", default_zoom))    # ズームの量(0.06 = 6%)
    total = hold * len(sc)
    n = int(round(total * FPS))

    imgs = [load(s, cfg) for s in sc]

    bgs = [None if isinstance(im, Clip) or sc[k].get("card") else studio_bg(im) for k, im in enumerate(imgs)]

    def frame_of(k, z):
        """k枚目の写真を画面に置く。物撮りは白い地に切らずに、それ以外は画面いっぱいに"""
        if sc[k].get("card"):
            return imgs[k]
        return place(imgs[k], z, bgs[k])

    ovs = [studio_overlay(s, cfg) if bgs[k] else overlay(s, cfg, None if isinstance(imgs[k], Clip) else frame_of(k, 1.0))
           for k, s in enumerate(sc)]

    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
    ]
    if cfg.get("bgm"):
        cmd += ["-stream_loop", "-1", "-i", cfg["bgm"]]
        audio = ["-af", f"afade=t=in:d=0.4,afade=t=out:st={total - 0.6}:d=0.6"]
    else:
        cmd += ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"]
        audio = []
    cmd += [
        "-map", "0:v", "-map", "1:a", "-t", f"{total}",
        "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
        "-profile:v", "high", "-r", str(FPS),
        "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2", *audio,
        "-movflags", "+faststart", out_path,
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    def shot(k, local_t, text_delay):
        if isinstance(imgs[k], Clip):
            base = imgs[k].next().convert("RGBA")
        else:
            z = 1.0 if sc[k].get("card") else 1 + zoom_amt * (local_t / (hold + fade / 2))
            base = frame_of(k, z).convert("RGBA")
        return Image.alpha_composite(base, with_alpha(ovs[k], ease((local_t - text_delay) / 0.6)))

    # k枚目が出始める時刻(前の写真とのクロスフェードの開始)
    starts = [0.0] + [k * hold - fade / 2 for k in range(1, len(sc))]
    for i in range(n):
        t = i / FPS
        k = max(j for j, st in enumerate(starts) if t >= st)  # いま出始めている、いちばん新しい写真
        mix = ease((t - starts[k]) / fade) if k else 1.0       # 0 = 前の写真、1 = 今の写真
        frame = shot(k, t - starts[k], 0.35 if k == 0 else fade * 0.6)
        if mix < 1:
            frame = Image.blend(shot(k - 1, t - starts[k - 1], 0), frame, mix)
        # 最初と最後をわずかにフェード
        edge = min(ease(t / 0.3), ease((total - t) / 0.3))
        rgb = frame.convert("RGB")
        if edge < 1:
            rgb = Image.blend(Image.new("RGB", (W, H), bgs[0 if t < 1 else -1] or GRAY), rgb, edge)
        proc.stdin.write(rgb.tobytes())
    proc.stdin.close()
    for im in imgs:
        if isinstance(im, Clip):
            im.proc.kill()
    if proc.wait() != 0:
        sys.exit("動画の書き出しに失敗しました")
    print(f"できました: {out_path}({total:.1f}秒)")


# カルーセル(写真の投稿)の大きさと、文字の位置。サイトの写真が正方形なので、切れない正方形(1:1)にする
CAROUSEL = dict(H=1080, TEXT_Y=700, PANEL_TOP=700, LABEL_Y=40)
CAROUSEL_STUDIO = dict(PW=700, PY=165, TOP_Y=92, BOT_Y=905)   # 正方形の画面での物撮りの置き方


def render_stills(cfg, out_path):
    """カルーセル用に、3場面を1枚ずつの写真(JPEG)として書き出す。
    out_path が 20261012-xxx.jpg なら、20261012-xxx-1.jpg 〜 -3.jpg ができる"""
    global H, TEXT_Y, PANEL_TOP, LABEL_Y, STUDIO
    H, TEXT_Y, PANEL_TOP, LABEL_Y = (CAROUSEL[k] for k in ("H", "TEXT_Y", "PANEL_TOP", "LABEL_Y"))
    STUDIO = CAROUSEL_STUDIO
    sc = scenes_for(cfg)
    stem = out_path[:-4] if out_path.lower().endswith(".jpg") else out_path
    outs = []
    for k, s in enumerate(sc):
        im = load(s, cfg)
        if isinstance(im, Clip):              # 動画の素材は、1秒あたりのコマを使う
            for _ in range(FPS):
                frame = im.next()
            im.proc.kill()
            base = cover(frame, 1.0)
        elif s.get("card"):
            base = im
        else:
            bg = studio_bg(im)
            base = place(im, 1.0, bg)
            if bg:
                out = Image.alpha_composite(base.convert("RGBA"), studio_overlay(s, cfg)).convert("RGB")
                path = f"{stem}-{k + 1}.jpg"
                out.save(path, quality=92)
                outs.append(path)
                continue
        out = Image.alpha_composite(base.convert("RGBA"), overlay(s, cfg, base)).convert("RGB")
        path = f"{stem}-{k + 1}.jpg"
        out.save(path, quality=92)
        outs.append(path)
    print("できました: " + ", ".join(outs))
    return outs


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    with open(sys.argv[1], encoding="utf-8") as fh:
        conf = json.load(fh)
    if conf.get("format") == "carousel":
        render_stills(conf, sys.argv[2])
    else:
        render(conf, sys.argv[2])
