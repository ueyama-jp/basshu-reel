#!/usr/bin/env python3
"""落ち着いたギターのBGMを自前で合成する(権利の心配がないオリジナル音源)

ゆっくりした分散和音。部屋に静かに流れるような、上品でやわらかい響き。
使い方: python3 make_bgm.py 出力.wav
        ffmpeg -i 出力.wav -c:a aac -b:a 160k assets/bgm_1_quiet_guitar.m4a
"""
import sys
import wave

import numpy as np

SR = 48000
rng = np.random.default_rng(5)


def hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def pluck(freq, dur, vel=1.0, bright=0.5):
    """弦を1本はじいた音(カープラス・ストロング法)。bright が小さいほど、指の腹で弾いたやわらかい音"""
    n = int(SR / freq)
    total = int(SR * dur)
    # はじく瞬間の音: 雑音を丸めたもの(丸めるほどやわらかい)
    burst = rng.uniform(-1, 1, n)
    k = max(1, int(n * (0.30 - 0.22 * bright)))
    burst = np.convolve(np.concatenate([burst, burst[:k]]), np.ones(k) / k, mode="valid")[:n]
    burst -= burst.mean()
    burst /= np.max(np.abs(burst)) + 1e-9
    periods = total // n + 1
    out = np.empty(periods * n)
    cur = burst
    # 低い弦ほど長く鳴り、高い弦ほど早く消える
    loss = 0.9975 - 0.0020 * min(1.0, freq / 400)
    mixf = 0.5 - 0.18 * (1 - bright)          # 高い倍音が抜ける速さ
    for i in range(periods):
        out[i * n:(i + 1) * n] = cur
        cur = loss * ((1 - mixf) * cur + mixf * np.roll(cur, 1))
    out = out[:total]
    t = np.arange(total) / SR
    out *= np.minimum(1.0, t / 0.004) * np.minimum(1.0, (dur - t) / 0.12)
    return out * vel


# コードごとの音: (低音, 和音の3音, いちばん上の音)。7thや9thを入れた、やわらかい響き
CHORDS = {
    "Gmaj7": (43, [54, 59, 62], 66),
    "Em9":   (40, [55, 59, 62], 66),
    "Cmaj9": (48, [55, 59, 62], 64),
    "D69":   (50, [57, 59, 64], 66),
}
SONG = ["Gmaj7", "Em9", "Cmaj9", "D69", "Gmaj7", "Em9", "Cmaj9"]
BEAT = 60 / 58          # ゆっくり
bar = BEAT * 4
total = bar * len(SONG) + 5
mix = np.zeros(int(SR * total))


def put(at, midi, dur, vel, bright):
    at += rng.uniform(-0.008, 0.008)            # 人が弾いたような揺れ
    s = max(0, int(at * SR))
    tone = pluck(hz(midi), dur, vel * rng.uniform(0.9, 1.04), bright)
    mix[s:s + len(tone)] += tone[:len(mix) - s]


for b, name in enumerate(SONG):
    root, mid, top = CHORDS[name]
    t0 = b * bar
    # 低音をひとつ長く伸ばし、その上に、間をあけて和音をほどいていく
    put(t0, root, 4.6, 0.55, 0.2)
    put(t0 + BEAT * 0.5, mid[0], 3.8, 0.30, 0.32)
    put(t0 + BEAT * 1.0, mid[1], 3.6, 0.32, 0.35)
    put(t0 + BEAT * 1.5, mid[2], 3.4, 0.32, 0.35)
    put(t0 + BEAT * 2.0, top, 3.6, 0.40, 0.4)
    put(t0 + BEAT * 3.0, mid[1], 2.6, 0.24, 0.32)
    if b % 2 == 1:
        put(t0 + BEAT * 3.5, mid[2], 2.4, 0.22, 0.32)
# 最後に和音をひとつ、ゆっくりほどいて終える
end = len(SONG) * bar
for i, m in enumerate([43, 54, 59, 62, 66]):
    put(end + i * 0.09, m, 4.5, 0.5 if i == 0 else 0.34, 0.3)

# 胴の鳴り: 低めの帯域を少し持ち上げる
t = np.arange(int(SR * 0.05)) / SR
body = np.exp(-t * 70) * (np.sin(2 * np.pi * 110 * t) + 0.6 * np.sin(2 * np.pi * 205 * t))
mix = mix + 0.010 * np.convolve(mix, body, mode="full")[:len(mix)]

# 小さな部屋の響き
ir_len = int(SR * 1.1)
ir = rng.standard_normal(ir_len) * np.exp(-np.arange(ir_len) / (SR * 0.34))
ir[:int(SR * 0.012)] = 0
wet = np.convolve(mix, ir, mode="full")[:len(mix)]
wet /= np.max(np.abs(wet)) + 1e-9
mix = mix / (np.max(np.abs(mix)) + 1e-9) * 0.85 + wet * 0.17

# 高音を少し丸めて、耳あたりをやわらかく
kernel = np.hanning(15)
mix = np.convolve(mix, kernel / kernel.sum(), mode="same")
mix = mix / np.max(np.abs(mix)) * 0.5           # 静かめの音量
stereo = np.stack([mix, np.roll(mix, 70)], axis=1)  # わずかな広がり

with wave.open(sys.argv[1], "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((stereo * 32767).astype("<i2").tobytes())
print(f"BGMをつくりました: {sys.argv[1]}({total:.0f}秒)")
