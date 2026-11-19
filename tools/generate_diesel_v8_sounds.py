#!/usr/bin/env python3
"""Generate original, synthesized diesel V8 sound placeholders for BMW X5 E53 mod.
These are procedural sound-design assets, not recordings of a real BMW engine.
Uses only Python standard library.
"""
import math, random, wave, struct, os

RATE = 44100
OUT = "build/bmw_m67d44_sounds"
random.seed(67044)
os.makedirs(OUT, exist_ok=True)

def clamp(x): return max(-1.0, min(1.0, x))

def write_wav(name, samples):
    path = os.path.join(OUT, name + ".wav")
    peak = max((abs(x) for x in samples), default=1.0) or 1.0
    # Normalize with headroom to avoid clipping.
    scale = 0.88 / peak
    with wave.open(path, "wb") as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(RATE)
        f.writeframes(b"".join(struct.pack("<h", int(clamp(x*scale)*32767)) for x in samples))
    print(path, len(samples)/RATE, "seconds")

def engine(name, seconds, rpm_start, rpm_end, load=0.45, turbo=0.0, start=False, stop=False):
    n = int(seconds*RATE)
    phase = 0.0
    lp = 0.0
    samples = []
    for i in range(n):
        t = i/RATE
        p = i/max(1,n-1)
        rpm = rpm_start + (rpm_end-rpm_start)*p
        # Four combustion events per crank revolution on a four-stroke V8.
        pulse_hz = max(1.0, rpm/60.0*4.0)
        phase += 2*math.pi*pulse_hz/RATE
        pulse = (math.sin(phase) + .45*math.sin(2*phase+.3) + .22*math.sin(3*phase+.7))
        # Deep block rumble and mechanical harmonics.
        crank = .28*math.sin(2*math.pi*(rpm/60.0)*t*.5)
        harmonics = .22*math.sin(phase*.5) + .13*math.sin(phase*1.5) + .08*math.sin(phase*2.5)
        raw = .43*pulse + crank + harmonics
        # Exhaust texture: filtered noise, more pronounced under load.
        noise = random.uniform(-1,1)
        lp = .91*lp + .09*noise
        raw += lp*(.06 + .12*load)
        # Subtle turbo whistle rises with rpm/load.
        if turbo:
            f = 900 + rpm*.9
            raw += turbo*(.035*math.sin(2*math.pi*f*t) + .018*math.sin(2*math.pi*f*1.47*t))
        # Slow engine modulation and mild unevenness.
        raw *= 1 + .035*math.sin(2*math.pi*3.1*t) + .018*math.sin(2*math.pi*7.3*t)
        env = 1.0
        if start:
            env = min(1.0, p*5.5)
            rpm_env = min(1.0, p*1.8)
            raw *= env*rpm_env
        if stop:
            env = max(0.0, 1.0-p)**1.6
            raw *= env
        # Gentle ramp-in/out for seamless loop assets.
        if not start and not stop:
            edge = min(1.0, p*12, (1-p)*12)
            raw *= edge
        samples.append(raw)
    write_wav(name, samples)

engine("bmw_m67d44_start", 3.4, 180, 720, .72, .35, start=True)
engine("bmw_m67d44_stop", 2.2, 720, 80, .25, .10, stop=True)
engine("bmw_m67d44_idle", 8.0, 690, 710, .20, .10)
engine("bmw_m67d44_low", 8.0, 900, 1450, .48, .22)
engine("bmw_m67d44_accel", 7.0, 950, 3300, .82, .70)
engine("bmw_m67d44_high", 8.0, 2600, 3600, .72, .65)
engine("bmw_m67d44_turbo", 5.0, 1400, 3200, .65, 1.0)
# Short drivetrain clunk/gear-change transient, synthesized from filtered noise and decaying tones.
def gear():
    s=[]
    for i in range(int(.55*RATE)):
        t=i/RATE
        e=math.exp(-t*10)
        s.append(e*(.5*math.sin(2*math.pi*95*t)+.25*math.sin(2*math.pi*185*t)+.16*random.uniform(-1,1)))
    write_wav("bmw_m67d44_gear",s)
gear()
