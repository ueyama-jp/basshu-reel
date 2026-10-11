#!/usr/bin/env python3
"""ボサノヴァ調のギターのBGMを自前で合成する(権利の心配がないオリジナル音源)

指で弾くやわらかいジャズギター。親指の低音と、ずらして入る和音。軽いシェイカー。
使い方: python3 make_bgm_bossa_guitar.py 出力.wav
        ffmpeg -i 出力.wav -c:a aac -b:a 160k assets/bgm_4_bossa_guitar.m4a
"""
import sys

import numpy as np

from bgm_common import SR, add, hiss, hz, pluck, room, save

rng = np.random.default_rng(34)
BEAT = 60 / 120
E = BEAT / 2            # 8分音符
# (低音, 交互の低音, 和音, 上に添える音)
CH = {
    "Am9":   (45, 52, [55, 59, 60, 64], 71),
    "D9":    (50, 45, [54, 60, 64], 69),
    "Gmaj7": (43, 50, [54, 59, 62], 66),
    "E7b9":  (40, 47, [56, 62, 65], 68),
}
SONG = ["Am9", "D9", "Gmaj7", "E7b9", "Am9", "D9", "Gmaj7", "Gmaj7"]
# ボサノヴァの和音の入り方(8分音符の位置)。2小節でひとまとまり
HITS = [[0, 3, 6], [1, 4, 7]]
bar = BEAT * 4
total = bar * len(SONG) + 4.5
n_all = int(SR * total)
gtr, shaker = np.zeros(n_all), np.zeros(n_all)

for b, name in enumerate(SONG):
    low, alt, chord, top = CH[name]
    t0 = b * bar
    add(gtr, t0, pluck(rng, hz(low), 1.5, 0.55, 0.18))                 # 親指: 1拍目と3拍目
    add(gtr, t0 + 2 * BEAT, pluck(rng, hz(alt), 1.4, 0.45, 0.18))
    for step in HITS[b % 2]:
        at = t0 + step * E + rng.uniform(-0.006, 0.006)
        for i, m in enumerate(chord):                                  # 和音は指でほぼ同時に
            add(gtr, at + i * 0.007, pluck(rng, hz(m), 0.85, 0.27 * rng.uniform(0.9, 1.05), 0.3))
    if b % 2 == 0:
        add(gtr, t0 + 5 * E, pluck(rng, hz(top), 1.6, 0.34, 0.38))     # ときどき、上の音をひとつ
    for step in range(8):                                              # シェイカー
        add(shaker, t0 + step * E, hiss(rng, 0.07, 55, 5) * (0.5 if step % 2 else 0.28))
end = len(SONG) * bar
for i, m in enumerate([43, 54, 59, 62, 66, 69]):                       # 最後は和音をゆっくりほどく
    add(gtr, end + i * 0.07, pluck(rng, hz(m), 4.2, 0.5 if i == 0 else 0.33, 0.3))

norm = lambda x: x / (np.max(np.abs(x)) + 1e-9)
mix = norm(gtr) * 0.9 + norm(shaker) * 0.05
save(sys.argv[1], room(rng, mix, 0.30, 0.15), 0.5, smooth=17)
