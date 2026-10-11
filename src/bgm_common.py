"""自作BGMで共通に使う音の部品(ピアノ風の音、弦をはじく音、ブラシやシェイカーの音、書き出し)"""
import wave

import numpy as np

SR = 48000


def hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def piano(rng, freq, dur, vel=1.0, soft=1.0):
    """ピアノ風の1音。soft が大きいほど、高い倍音が早く消えて丸い音になる"""
    t = np.arange(int(SR * dur)) / SR
    out = np.zeros_like(t)
    for k in range(1, 9):
        f = freq * k * np.sqrt(1 + 0.0004 * k * k)
        if f > SR / 2.2:
            break
        amp = (1.0 / k ** (1.5 + 0.3 * soft)) * (0.6 if k % 2 == 0 else 1.0)
        decay = np.exp(-t * (1.1 + 0.6 * k * soft) * (freq / 220) ** 0.35)
        out += amp * decay * np.sin(2 * np.pi * f * t + rng.uniform(0, 0.3))
    return out * np.minimum(1.0, t / 0.009) * np.minimum(1.0, (dur - t) / 0.12) * vel


def pluck(rng, freq, dur, vel=1.0, bright=0.4, sustain=0.9970):
    """弦を1本はじいた音(カープラス・ストロング法)。bright が小さいほど、指の腹で弾いた丸い音"""
    n = int(SR / freq)
    total = int(SR * dur)
    burst = rng.uniform(-1, 1, n)
    k = max(1, int(n * (0.30 - 0.22 * bright)))
    burst = np.convolve(np.concatenate([burst, burst[:k]]), np.ones(k) / k, mode="valid")[:n]
    burst -= burst.mean()
    burst /= np.max(np.abs(burst)) + 1e-9
    periods = total // n + 1
    out = np.empty(periods * n)
    cur = burst
    loss = sustain - 0.0020 * min(1.0, freq / 400)
    mixf = 0.5 - 0.18 * (1 - bright)
    for i in range(periods):
        out[i * n:(i + 1) * n] = cur
        cur = loss * ((1 - mixf) * cur + mixf * np.roll(cur, 1))
    out = out[:total]
    t = np.arange(total) / SR
    return out * np.minimum(1.0, t / 0.004) * np.minimum(1.0, (dur - t) / 0.08) * vel


def hiss(rng, dur, decay, cut=8):
    """ブラシやシェイカーのような、さらさらした短い音"""
    t = np.arange(int(SR * dur)) / SR
    noise = rng.standard_normal(len(t))
    noise = noise - np.convolve(noise, np.ones(cut) / cut, mode="same")   # 低い成分を抜く
    return noise * np.exp(-t * decay) * np.minimum(1.0, t / 0.004)


def add(buf, at, tone):
    s = max(0, int(at * SR))
    buf[s:s + len(tone)] += tone[:len(buf) - s]


def room(rng, mix, seconds, amount):
    """部屋の響きを足す"""
    n = int(SR * seconds * 4)
    ir = rng.standard_normal(n) * np.exp(-np.arange(n) / (SR * seconds))
    ir[:int(SR * 0.01)] = 0
    wet = np.convolve(mix, ir, mode="full")[:len(mix)]
    wet /= np.max(np.abs(wet)) + 1e-9
    return mix / (np.max(np.abs(mix)) + 1e-9) * 0.85 + wet * amount


def save(path, mix, level, width=70, smooth=13):
    kernel = np.hanning(smooth)
    mix = np.convolve(mix, kernel / kernel.sum(), mode="same")     # 高音を少し丸める
    mix = mix / np.max(np.abs(mix)) * level
    stereo = np.stack([mix, np.roll(mix, width)], axis=1)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((stereo * 32767).astype("<i2").tobytes())
    print(f"BGMをつくりました: {path}({len(mix) / SR:.0f}秒)")
