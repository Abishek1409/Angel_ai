"""Synthesizes the soundtrack + SFX on one 120 BPM grid (beat = 0.5s) in C major. Output: work/audio.wav"""
import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt, fftconvolve

SR = 48000
DUR = 21.0
BEAT = 0.5
N = int(SR * DUR)
rng = np.random.default_rng(7)

def buf(): return np.zeros((N, 2))
def hz(m): return 440.0 * 2 ** ((m - 69) / 12)
def env(n, a=0.005, d=0.3, s=0.0, r=0.05, hold=None):
    t = np.arange(n) / SR
    e = np.where(t < a, t / a, s + (1 - s) * np.exp(-(t - a) / max(d, 1e-4)))
    if hold is not None:
        rel = t > hold
        e[rel] *= np.exp(-(t[rel] - hold) / r)
    return e
def lp(x, f, o=2): return sosfilt(butter(o, f, 'low', fs=SR, output='sos'), x, axis=0)
def hp(x, f, o=2): return sosfilt(butter(o, f, 'high', fs=SR, output='sos'), x, axis=0)
def bp(x, lo, hi): return sosfilt(butter(2, [lo, hi], 'band', fs=SR, output='sos'), x, axis=0)
def place(dst, sig, t, gain=1.0, pan=0.0):
    i = int(round(t * SR))
    if i >= N: return
    sig = sig[: N - i]
    if sig.ndim == 1:
        l, r = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
        sig = np.stack([sig * l, sig * r], 1) * np.sqrt(2)
    dst[i:i + len(sig)] += sig * gain

def saw(f, n, detune=0.0):
    t = np.arange(n) / SR
    out = 0
    for d in (-detune, 0, detune):
        ph = (t * f * (1 + d)) % 1.0
        out = out + (2 * ph - 1)
    return out / 3

# Chords, one per bar (2s): C Am F G, repeated
CHORDS = [[48, 52, 55, 60, 64], [45, 52, 57, 60, 64], [41, 53, 57, 60, 65], [43, 50, 55, 59, 62]]
ROOTS = [36, 33, 29, 31]
def chord_at(t): return int(t // 2.0) % 4

drums, bass, pad, keys, sfx = buf(), buf(), buf(), buf(), buf()

# ---------- Drums ----------
def kick():
    n = int(.35 * SR); t = np.arange(n) / SR
    f = 45 + 110 * np.exp(-t * 35)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, .001, .16) + 0.15 * lp(rng.standard_normal(n), 2000) * env(n, .0005, .006)
def hat(open_=False):
    n = int((.18 if open_ else .05) * SR)
    return hp(rng.standard_normal(n), 7500) * env(n, .001, .05 if open_ else .015)
def clap():
    n = int(.25 * SR); x = bp(rng.standard_normal(n), 900, 3500)
    e = sum(env(n, .001, .008) * (np.arange(n) >= int(k * SR)) for k in (0, .011, .022)) / 2 + env(n, .001, .09) * .6
    return x * e

K, H, HO, C = kick(), hat(), hat(True), clap()
for b in range(int(DUR / BEAT)):
    t = b * BEAT
    intro, outro = t < 2.5, t >= 18.5
    if outro: continue
    place(drums, K, t, .9 if not intro else .7)
    if t >= 6.0:
        if b % 2 == 1: place(drums, C, t, .32, .1)
        place(drums, H, t + BEAT / 2, .12, -.3)
        place(drums, H, t, .06, -.3)
        if b % 8 == 7: place(drums, HO, t + BEAT / 2, .1, -.3)
    elif t >= 2.5:
        place(drums, H, t + BEAT / 2, .08, -.3)

# ---------- Bass (8ths, root, from reveal) ----------
for i in range(int(DUR / (BEAT / 2))):
    t = i * BEAT / 2
    if t < 2.5 or t >= 18.5: continue
    m = ROOTS[chord_at(t)] + (12 if i % 4 == 3 else 0)
    n = int(.24 * SR)
    s = lp(saw(hz(m), n, .003) + .5 * np.sin(2 * np.pi * hz(m) * np.arange(n) / SR), 700)
    place(bass, s * env(n, .004, .12, .35, .03, hold=.2), t, .32)
# Outro: sustained low C
n = int(2.5 * SR); place(bass, np.sin(2 * np.pi * hz(36) * np.arange(n) / SR) * env(n, .01, 1.2), 18.5, .38)

# ---------- Pad ----------
for bar in range(11):
    t0 = bar * 2.0
    if t0 >= 18.5: break
    start = max(t0, 2.5) if t0 < 2.5 else t0
    if start >= t0 + 2.0: continue
    n = int((t0 + 2.0 - start + .4) * SR)
    s = sum(saw(hz(m), n, .004) for m in CHORDS[chord_at(t0)][1:])
    s = lp(s, 1400 if start >= 6.0 else 900)
    e = np.minimum(1, np.arange(n) / (.15 * SR)) * np.minimum(1, (n - np.arange(n)) / (.4 * SR))
    place(pad, s * e, start, .045, 0)
# Outro chord: C major 9 stab that rings out
n = int(2.6 * SR)
s = lp(sum(saw(hz(m), n, .005) for m in [48, 55, 60, 64, 67, 74]), 2200) * env(n, .005, 1.1, 0, .2)
place(pad, s, 18.5, .07)

# ---------- Keys: plucked arpeggio (16ths feel on 8ths) ----------
def pluck(m, dur=.35):
    n = int(dur * SR); t = np.arange(n) / SR
    s = np.sin(2 * np.pi * hz(m) * t) + .35 * np.sin(2 * np.pi * hz(m) * 2 * t) * np.exp(-t * 18)
    return s * env(n, .002, .16)
for i in range(int(DUR / (BEAT / 2))):
    t = i * BEAT / 2
    if t >= 18.5: break
    if t < 2.5 and i % 2: continue  # intro: hook words on quarter notes only
    tones = CHORDS[chord_at(t)][2:] + [CHORDS[chord_at(t)][2] + 12]
    m = tones[[0, 1, 2, 3, 2, 1, 3, 1][i % 8]] + 12
    place(keys, pluck(m), t, .16 if t >= 2.5 else .22, (-.35, .35)[i % 2])
# Outro melody resolve
for k, m in enumerate([76, 79, 84]): place(keys, pluck(m, .9), 18.5 + k * .25, .2, (-.2, 0, .2)[k])

# ---------- SFX (in key, on the grid) ----------
def tick():  # soft UI click, pitched to G
    n = int(.06 * SR); t = np.arange(n) / SR
    return (np.sin(2 * np.pi * hz(91) * t) * .6 + bp(rng.standard_normal(n), 2500, 6000) * .4) * env(n, .0005, .012)
def whoosh(dur=.5):
    n = int(dur * SR); x = rng.standard_normal(n)
    w = np.sin(np.pi * np.arange(n) / n) ** 2
    return bp(x, 400, 3000) * w
def chime(ms):
    out = np.zeros(int(1.2 * SR))
    for k, m in enumerate(ms):
        p = pluck(m, 1.0); i = int(k * .125 * SR); out[i:i + len(p)] += p[: len(out) - i]
    return out
def swell(dur=.5):  # reverse-ish riser into reveal
    n = int(dur * SR); x = lp(rng.standard_normal(n), 3000)
    return x * (np.arange(n) / n) ** 3

# hook words (0, .5, 1, 1.5) — low accent under each word, tonic notes
for k, m in enumerate([60, 60, 64, 67]): place(sfx, pluck(m - 12, .4), k * .5, .14)
place(sfx, swell(.5), 2.0, .1)                      # into reveal
place(sfx, whoosh(.5), 5.75, .06)                    # reveal -> demo
for t in (6.75, 7.25, 10.5, 13.0, 14.0, 16.0):       # every click is on a beat or 8th
    place(sfx, tick(), t, .12, .15)
place(sfx, chime([72, 76, 79]), 8.25, .12, .1)       # "Ready" — C major arpeggio
place(sfx, whoosh(.4), 8.75, .045)                   # upload -> workspace
for i in range(9):                                    # soft typing, on 16ths
    place(sfx, tick() * .5, 9.25 + i * .125, .05, -.2)
place(sfx, chime([79, 84]), 11.0, .08, -.1)          # answer lands
place(sfx, whoosh(.6), 14.0, .05)                    # card flip
for k in range(4): place(sfx, pluck([67, 72, 76, 79][k], .3), 16.0 + k * .25, .07, (-.3, .3)[k % 2])  # nodes pop
place(sfx, swell(.5), 18.0, .08)                     # into outro

# ---------- Mix ----------
def reverb(x, secs=1.6, wet=.18):
    n = int(secs * SR); t = np.arange(n) / SR
    ir = rng.standard_normal((n, 2)) * np.exp(-t * 4.5)[:, None]
    ir = lp(ir, 5000)
    y = np.stack([fftconvolve(x[:, c], ir[:, c])[:N] for c in range(2)], 1)
    return x + y / np.max(np.abs(y) + 1e-9) * np.max(np.abs(x) + 1e-9) * wet

# Sidechain-ish pump on pad/keys from the kick
pump = np.ones(N)
for b in range(int(DUR / BEAT)):
    t = b * BEAT
    if t >= 18.5: break
    i = int(t * SR); n = int(.25 * SR)
    pump[i:i + n] = np.minimum(pump[i:i + n], .55 + .45 * (np.arange(n) / n) ** .7)

music = drums + bass + (pad + keys) * pump[:, None]
mix = reverb(music, wet=.12) + reverb(lp(sfx, 9000), wet=.25) * .9
mix = hp(mix, 30)
# Master: fade-in first 10ms, fade-out last 0.4s, soft clip, normalize to -1 dBFS
fade = np.ones(N); fade[: int(.01 * SR)] = np.linspace(0, 1, int(.01 * SR)); fade[-int(.4 * SR):] = np.linspace(1, 0, int(.4 * SR))
mix *= fade[:, None]
mix = np.tanh(mix * 1.4) / np.tanh(1.4)
mix *= 10 ** (-1 / 20) / np.max(np.abs(mix))
wavfile.write('audio.wav', SR, (mix * 32767).astype(np.int16))
print('peak ok, seconds:', N / SR)
