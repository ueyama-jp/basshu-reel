#!/usr/bin/env python3
"""ジャズ調のピアノのBGMを自前で合成する(権利の心配がないオリジナル音源)

ピアノ、ウッドベース、ブラシの小さな編成。ゆったり跳ねるリズムで、軽やかだが落ち着いている。
使い方: python3 make_bgm_jazz_piano.py 出力.wav
        ffmpeg -i 出力.wav -c:a aac -b:a 160k assets/bgm_2_jazz_piano.m4a
"""
import sys

import numpy as np

from bgm_common import SR, add, hiss, hz, piano, pluck, room, save

rng = np.random.default_rng(21)
BEAT = 60 / 92
SW = 2 / 3              # 裏拍の位置(3連符の3つ目。ジャズの跳ね)
# (和音: 根音を省いたやわらかい押さえ方, 歩くベース4つ, 右手の短いフレーズ [拍, 音])
SONG = [
    ([53, 57, 60, 64], [38, 41, 45, 44], [(1 + SW, 69), (2, 72), (3, 76)]),          # Dm9
    ([53, 57, 59, 64], [43, 47, 50, 49], [(0 + SW, 74), (2, 71), (2 + SW, 69)]),     # G13
    ([52, 55, 59, 62], [48, 52, 55, 57], [(0, 67), (1 + SW, 71), (3, 74)]),          # Cmaj9
    ([55, 59, 61, 66], [45, 49, 52, 51], [(1, 73), (2 + SW, 76)]),                   # A13
    ([53, 57, 60, 64], [38, 45, 41, 44], [(0 + SW, 77), (1 + SW, 76), (3, 72)]),     # Dm9
    ([53, 57, 59, 64], [43, 50, 47, 49], [(0, 71), (2, 74), (3 + SW, 76)]),          # G13
    ([52, 55, 59, 62], [48, 43, 45, 47], [(0, 79), (2 + SW, 76), (3 + SW, 74)]),     # Cmaj9
]
bar = BEAT * 4
total = bar * len(SONG) + 4.5
n_all = int(SR * total)
keys, bass, brush = np.zeros(n_all), np.zeros(n_all), np.zeros(n_all)

for b, (chord, walk, phrase) in enumerate(SONG):
    t0 = b * bar
    # ピアノの和音: 1拍目と、2拍目の裏(ジャズでよく使う合いの手)
    for at, dur, vel in [(0, 0.9, 0.26), (1 + SW, 1.3, 0.22)]:
        for i, m in enumerate(chord):
            add(keys, t0 + at * BEAT + i * 0.006 + rng.uniform(-0.006, 0.006), piano(rng, hz(m), dur, vel, 1.3))
    for at, m in phrase:                                       # 右手のフレーズ
        add(keys, t0 + at * BEAT + rng.uniform(-0.008, 0.008), piano(rng, hz(m), 1.1, 0.34 * rng.uniform(0.85, 1.05), 1.1))
    for beat, m in enumerate(walk):                            # ウッドベースが1拍ずつ歩く
        add(bass, t0 + beat * BEAT + rng.uniform(-0.006, 0.006), pluck(rng, hz(m), 0.62, 0.6, 0.12, 0.9985))
    for beat in range(4):                                      # ブラシ: チーン、チッチ、チーン
        add(brush, t0 + beat * BEAT, hiss(rng, 0.20, 16) * 0.30)
        if beat % 2 == 1:
            add(brush, t0 + (beat + SW) * BEAT, hiss(rng, 0.10, 34) * 0.18)
            add(brush, t0 + beat * BEAT, hiss(rng, 0.06, 60, 4) * 0.22)
end = len(SONG) * bar
for i, m in enumerate([36, 52, 55, 59, 62, 69]):               # 最後は和音をひとつ、ゆっくり
    add(keys, end + i * 0.04, piano(rng, hz(m), 4.2, 0.36 if i else 0.5, 1.2))
add(bass, end, pluck(rng, hz(36), 3.0, 0.6, 0.12, 0.9990))

kb = np.hanning(41)
bass = np.convolve(bass, kb / kb.sum(), mode="same")           # ベースは丸く
norm = lambda x: x / (np.max(np.abs(x)) + 1e-9)
mix = norm(keys) * 0.8 + norm(bass) * 0.55 + norm(brush) * 0.11
save(sys.argv[1], room(rng, mix, 0.26, 0.13), 0.5)
