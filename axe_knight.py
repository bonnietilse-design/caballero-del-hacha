#!/usr/bin/env python3
"""
El Caballero del Hacha (Axe Knight) - a small Mario-style platformer made with pygame.

You are a very muscly little knight in blue armour swinging a huge double-bladed
axe. Instead of jumping on the toads, you chop them!

Controls
  Left / Right  or  A / D      move
  Space / Up / W               jump (hold for a higher jump)
  X / J / Left Ctrl            swing the axe
  M                            sound on / off
  Enter                        start / restart
  Esc                          quit

Run:  python axe_knight.py
pygame (and gTTS for the Spanish voices) install themselves on the first run.

Sound
  Beeps, croaks and the flamenco guitar are generated in code.
  The Spanish voice clips are made once with Google text-to-speech (needs
  internet the first time) and saved in the "sonidos" folder next to this file.
  To use your OWN voice: record a clip and save it in "sonidos" under the same
  name as a .wav file (for example ay.wav). Your .wav wins over the generated
  .mp3. The clip names and what they say are listed in VOICE_LINES below.

Edit LEVEL_MAP to build your own level.
"""

import math
import os
import random
import subprocess
import sys
import threading
from array import array

HERE = os.path.dirname(os.path.abspath(__file__))


# ------------------------------------------------------------------ auto-install
def _add_user_site():
    """Some Pythons (e.g. ArcGIS Pro's) can't write to their own folder, so pip
    installs into the personal user folder - which they don't search by default."""
    import importlib
    import site
    user_site = site.getusersitepackages()
    if user_site not in sys.path:
        sys.path.append(user_site)
    importlib.invalidate_caches()


def _try_import(name):
    import importlib
    for _ in range(2):
        try:
            return importlib.import_module(name)
        except ImportError:
            _add_user_site()   # maybe it is already installed in the user folder
    return None


def _pip_install(package):
    # sys.executable is the Python running this file, so the package lands in
    # the same environment (e.g. your PyCharm project interpreter).
    result = subprocess.run([sys.executable, "-m", "pip", "install", package])
    _add_user_site()
    return result.returncode == 0


def ensure_pygame():
    """Install pygame automatically the first time, if it is missing."""
    if _try_import("pygame"):
        return
    print("pygame is not installed yet - installing it now (this only happens once)...")
    for package in ("pygame", "pygame-ce"):   # pygame-ce supports newer Pythons
        if _pip_install(package) and _try_import("pygame"):
            print(f"{package} installed.")
            return
    sys.exit("Could not install pygame automatically. "
             "Please run 'pip install pygame' in PyCharm's Terminal and try again.")


ensure_pygame()
import pygame  # noqa: E402

# ------------------------------------------------------------------ Spanish voices
VOICE_DIR = os.path.join(HERE, "sonidos")
VOICE_LINES = {            # file name -> what the voice says
    "vamos": "¡Vamos, caballero!",       # game starts
    "toma": "¡Toma!",                    # toad chopped
    "adios": "¡Adiós, sapito!",          # toad chopped
    "rey": "¡Adiós, rey sapo!",          # big king toad chopped
    "ay": "¡Ay, ay, ay!",                # you get hurt
    "oro": "¡Más oro!",                  # every 5th coin
    "desastre": "¡Qué desastre!",        # you lose a life
    "fin": "Fin del juego.",             # game over
    "ole": "¡Olé!",                      # you reach the flag
}


def find_voice_file(key):
    for ext in (".wav", ".ogg", ".mp3"):
        path = os.path.join(VOICE_DIR, key + ext)
        if os.path.isfile(path):
            return path
    return None


def prepare_voices():
    """Create any missing Spanish voice clips with Google text-to-speech."""
    try:
        os.makedirs(VOICE_DIR, exist_ok=True)
    except OSError:
        return
    missing = [k for k in VOICE_LINES if not find_voice_file(k)]
    if not missing:
        return
    print("Creating the Spanish voice clips (first run only, needs internet)...")
    gtts = _try_import("gtts")
    if gtts is None:
        print("Installing gTTS (Google text-to-speech)...")
        if _pip_install("gTTS"):
            gtts = _try_import("gtts")
        if gtts is None:
            print("Could not install gTTS - the game will play without voices.")
            return
    for key in missing:
        path = os.path.join(VOICE_DIR, key + ".mp3")
        try:
            gtts.gTTS(VOICE_LINES[key], lang="es", tld="es").save(path)
            print("   ", VOICE_LINES[key])
        except Exception:
            if os.path.exists(path):
                os.remove(path)
            print("Could not create the voices (no internet?) - playing without them this time.")
            return


# ------------------------------------------------------------------ settings
TILE = 40
SCREEN_W, SCREEN_H = 960, 520
FPS = 60
AUDIO_RATE = 22050

GRAVITY = 0.65
MAX_FALL = 15
RUN_ACCEL = 0.7
RUN_FRICTION = 0.8
AIR_CONTROL = 0.55
MAX_RUN = 4.6
JUMP_SPEED = 12.8
JUMP_CUT = 4.5            # releasing jump early limits upward speed to this
COYOTE_FRAMES = 6         # you can still jump shortly after leaving a ledge
JUMP_BUFFER_FRAMES = 7    # a jump pressed just before landing still counts

ATTACK_FRAMES = 22
ATTACK_ACTIVE = (6, 14)   # frames of the swing during which the axe hurts
ATTACK_COOLDOWN = 6
INVULN_FRAMES = 90
START_LIVES = 3
MAX_HEARTS = 3

ARM_LEN = 16              # shoulder -> hand
AXE_HEAD = 48             # hand -> centre of the axe head
AXE_LEN = 56              # hand -> top of the handle

# ------------------------------------------------------------------ level
# Legend:  #  ground          =  stone platform     C  breakable crate
#          o  coin            P  player start       F  goal flag
#          t  toad (1 hit)    T  king toad (3 hits) j  leaping toad
LEVEL_MAP = [
    "..................................................................................................................................",
    "..................................................................................................................................",
    "..................................................................................................................................",
    "..................................................................................................................................",
    "...................................................................................j..............................................",
    ".....................................................................................oooo.........................................",
    ".................................j.................ooo...............................====......................j..................",
    "..........................ooooo.............................ooooo.............ooooo..................................#............",
    "......ooo.................=====...........oo........#.......=====.......oo....=====...................oo............##.oooo.......",
    "....................................C.....==.......##...................==.................C..........==...........###............",
    "..P...........t....................CC..t..........###.....T....t...t................t.....CC...T..t.........t.....####.......F....",
    "####################..###################....##########################....##########################....#########################",
    "####################..###################....##########################....##########################....#########################",
]

SOLID = "#=C"

# ------------------------------------------------------------------ colours
WHITE = (255, 255, 255)
BLACK = (15, 15, 25)
SKY_TOP = (96, 160, 236)
SKY_BOTTOM = (196, 228, 255)
HILL_FAR = (150, 205, 160)
HILL_NEAR = (105, 180, 115)
DIRT = (150, 98, 60)
DIRT_DARK = (118, 74, 44)
DIRT_LIGHT = (176, 124, 82)
GRASS = (92, 190, 80)
GRASS_DARK = (60, 140, 55)
GRASS_LIGHT = (140, 220, 110)
STONE = (150, 150, 165)
STONE_DARK = (95, 95, 115)
STONE_LIGHT = (190, 190, 205)
WOOD = (196, 140, 72)
WOOD_DARK = (120, 80, 40)

ARMOR = (52, 104, 214)
ARMOR_MID = (82, 136, 236)
ARMOR_LIGHT = (130, 178, 255)
ARMOR_DARK = (26, 52, 120)
STEEL = (170, 180, 200)
STEEL_DARK = (40, 58, 110)
BOOT = (40, 34, 50)
VISOR = (18, 22, 40)
PLUME = (230, 60, 60)
SKIN = (236, 182, 140)
SKIN_LIGHT = (252, 214, 182)
SKIN_DARK = (176, 116, 82)
HANDLE = (130, 86, 44)
HANDLE_DARK = (80, 50, 24)
BLADE = (210, 218, 232)
BLADE_DARK = (90, 98, 120)

TOAD = (106, 160, 64)
TOAD_DARK = (58, 100, 40)
TOAD_BELLY = (222, 216, 150)
KING = (150, 112, 62)
KING_DARK = (92, 64, 32)
KING_BELLY = (228, 200, 150)
JUMPER = (238, 122, 40)
JUMPER_DARK = (120, 50, 20)
JUMPER_BELLY = (255, 214, 120)
TOAD_EYE = (250, 210, 60)
GOLD = (255, 205, 60)
GOLD_DARK = (190, 130, 20)
HEART = (230, 50, 70)
HEART_EMPTY = (90, 60, 70)


def lerp(a, b, t):
    return a + (b - a) * t


def ease_out(t):
    return 1 - (1 - t) ** 3


# ------------------------------------------------------------------ sound synthesis
def synth(rate, dur, f1, f2=None, wave="square", vol=0.4, tremolo=0.0, attack=0.004, curve=2.0):
    """A single tone (or noise) that slides from f1 to f2 and fades out."""
    f2 = f1 if f2 is None else f2
    n = int(rate * dur)
    out = [0.0] * n
    rng = random.Random(5)
    phase = 0.0
    a_n = max(1, int(attack * rate))
    for i in range(n):
        t = i / n
        phase += (f1 + (f2 - f1) * t) / rate
        p = phase % 1.0
        if wave == "square":
            v = 1.0 if p < 0.5 else -1.0
        elif wave == "tri":
            v = 4 * abs(p - 0.5) - 1
        elif wave == "sine":
            v = math.sin(math.tau * p)
        else:
            v = rng.uniform(-1, 1)
        env = min(1.0, i / a_n) * (1 - t) ** curve
        if tremolo:
            env *= 0.55 + 0.45 * math.sin(math.tau * tremolo * i / rate)
        out[i] = v * env * vol
    return out


def lowpass(samples, amount):
    out, y = [], 0.0
    for x in samples:
        y += amount * (x - y)
        out.append(y)
    return out


def silence(rate, dur):
    return [0.0] * int(rate * dur)


def mix(*parts):
    out = [0.0] * max(len(p) for p in parts)
    for p in parts:
        for i, v in enumerate(p):
            out[i] += v
    return out


def whoosh(rate, dur=0.22, vol=0.9):
    rng = random.Random(9)
    n = int(rate * dur)
    out, y = [], 0.0
    for i in range(n):
        t = i / n
        y += (0.03 + 0.35 * math.sin(math.pi * t)) * (rng.uniform(-1, 1) - y)
        out.append(y * vol * math.sin(math.pi * t) ** 1.5)
    return out


def pluck(rate, freq, dur, vol, rng, damp=0.996):
    """Karplus-Strong plucked string - sounds like a guitar."""
    size = max(2, int(rate / freq))
    buf = [rng.uniform(-1, 1) for _ in range(size)]
    n = int(rate * dur)
    out = [0.0] * n
    idx = 0
    for i in range(n):
        nxt = idx + 1 if idx + 1 < size else 0
        a = buf[idx]
        out[i] = a * vol
        buf[idx] = damp * 0.5 * (a + buf[nxt])
        idx = nxt
    fade = max(1, n // 8)
    for i in range(fade):
        out[n - fade + i] *= 1 - i / fade
    return out


def flamenco(rate):
    """Andalusian cadence (Am - G - F - E) with a rasgueado and palmas."""
    rng = random.Random(11)
    am = [110.0, 164.8, 220.0, 261.6, 329.6]
    g = [98.0, 123.5, 146.8, 196.0, 246.9, 392.0]
    f = [87.3, 130.8, 174.6, 220.0, 261.6, 349.2]
    e = [82.4, 123.5, 164.8, 207.7, 246.9, 329.6]
    out = [0.0] * int(rate * 3.6)

    def add(samples, start):
        o = int(start * rate)
        end = min(len(out), o + len(samples))
        for i in range(o, end):
            out[i] += samples[i - o]

    def strum(chord, start, dur, down=True):
        for k, freq in enumerate(chord if down else chord[::-1]):
            add(pluck(rate, freq, dur, 0.22, rng), start + k * 0.012)

    def clap(start):
        n = int(0.05 * rate)
        prev, samples = 0.0, []
        for i in range(n):
            x = rng.uniform(-1, 1)
            samples.append((x - prev) * 0.35 * (1 - i / n) ** 3)
            prev = x
        add(samples, start)

    for start, chord in ((0.0, am), (0.36, g), (0.72, f), (1.08, e)):
        strum(chord, start, 0.6)
        clap(start)
    for k, start in enumerate((1.40, 1.50, 1.60)):          # rasgueado
        strum(e, start, 0.3, down=k % 2 == 0)
    strum(e, 1.75, 1.7)
    for start in (1.40, 1.60, 1.75):
        clap(start)
    peak = max(abs(v) for v in out) or 1.0
    return [v * 0.9 / peak for v in out]


def build_sounds(rate):
    jingle = lambda notes, d: sum((synth(rate, d, n, wave="tri", vol=0.35, curve=0.6) for n in notes), [])
    return {
        "swing": whoosh(rate),
        "hit": mix(synth(rate, 0.16, 150, 40, "sine", 0.9, curve=1.5),
                   lowpass(synth(rate, 0.05, 1, wave="noise", vol=0.5), 0.3)),
        "croak": lowpass(synth(rate, 0.11, 210, 160, vol=0.3, tremolo=35) + silence(rate, 0.035)
                         + synth(rate, 0.17, 180, 110, vol=0.32, tremolo=30), 0.35),
        "croak_big": lowpass(synth(rate, 0.18, 140, 100, vol=0.4, tremolo=24) + silence(rate, 0.05)
                             + synth(rate, 0.32, 120, 65, vol=0.45, tremolo=20), 0.25),
        "jump": synth(rate, 0.13, 280, 640, vol=0.16, curve=1.0),
        "coin": synth(rate, 0.06, 988, vol=0.16, curve=0.3) + synth(rate, 0.25, 1319, vol=0.16, curve=1.5),
        "crate": mix(lowpass(synth(rate, 0.14, 1, wave="noise", vol=0.8), 0.5),
                     synth(rate, 0.08, 110, 70, vol=0.25)),
        "hurt": synth(rate, 0.32, 520, 140, vol=0.28, tremolo=18, curve=1.0),
        "die": jingle((523, 415, 330, 262), 0.14),
        "gameover": jingle((392, 330, 262, 196), 0.26),
        "win": flamenco(rate),
    }


class SoundBank:
    """Plays the generated sound effects and the Spanish voice clips.
    If anything about audio fails, the game simply stays silent."""

    def __init__(self):
        self.enabled = True
        self.ready = False
        self.sfx = {}
        self.voices = {}
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(AUDIO_RATE, -16, 2, 512)
            self.rate, size, self.channels = pygame.mixer.get_init()
            if abs(size) != 16:
                return
            pygame.mixer.set_num_channels(16)
            self.voice_channel = pygame.mixer.Channel(15)
        except Exception:
            return
        for key in VOICE_LINES:
            path = find_voice_file(key)
            if path:
                try:
                    self.voices[key] = pygame.mixer.Sound(path)
                except Exception:
                    pass
        self.ready = True
        # generating the sounds takes a moment, so do it in the background
        threading.Thread(target=self._build, daemon=True).start()

    def _build(self):
        try:
            for name, samples in build_sounds(self.rate).items():
                self.sfx[name] = self._to_sound(samples)
        except Exception:
            pass

    def _to_sound(self, samples):
        mono = array("h", (int(max(-1.0, min(1.0, s)) * 32000) for s in samples))
        if self.channels == 1:
            data = mono
        else:
            data = array("h", bytes(2 * len(mono) * self.channels))
            for c in range(self.channels):
                data[c::self.channels] = mono
        return pygame.mixer.Sound(buffer=data.tobytes())

    def play(self, name):
        if self.ready and self.enabled and name in self.sfx:
            self.sfx[name].play()

    def say(self, key, force=False):
        if self.ready and self.enabled and key in self.voices:
            if force or not self.voice_channel.get_busy():
                self.voice_channel.play(self.voices[key])

    def toggle(self):
        self.enabled = not self.enabled
        if not self.enabled and self.ready:
            pygame.mixer.stop()


# ------------------------------------------------------------------ physics
def physics_move(ent, level):
    """Move an entity by its velocity and resolve collisions with solid tiles."""
    ent.hit_wall = False
    ent.x += ent.vx
    r = ent.rect()
    for _, t in level.tiles_near(r):
        if r.colliderect(t):
            if ent.vx > 0:
                ent.x = t.left - ent.w
            elif ent.vx < 0:
                ent.x = t.right
            else:
                continue
            ent.hit_wall = True
            ent.vx = 0
            r = ent.rect()

    ent.vy = min(ent.vy + GRAVITY, MAX_FALL)
    ent.y += ent.vy
    r = ent.rect()
    ent.on_ground = False
    for _, t in level.tiles_near(r):
        if r.colliderect(t):
            if ent.vy > 0:
                ent.y = t.top - ent.h
                ent.on_ground = True
            elif ent.vy < 0:
                ent.y = t.bottom
            ent.vy = 0
            r = ent.rect()
    if not ent.on_ground and ent.vy >= 0:
        probe = r.move(0, 1)
        if any(probe.colliderect(t) for _, t in level.tiles_near(probe)):
            ent.on_ground = True


# ------------------------------------------------------------------ small objects
class Particle:
    def __init__(self, x, y, vx, vy, color, life, size, grav=0.25):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.color, self.life, self.max_life = color, life, life
        self.size, self.grav = size, grav

    def update(self):
        self.vy += self.grav
        self.x += self.vx
        self.y += self.vy
        self.life -= 1

    def draw(self, surf, cam):
        s = max(1, int(self.size * self.life / self.max_life + 1))
        pygame.draw.rect(surf, self.color, (int(self.x - cam - s / 2), int(self.y - s / 2), s, s))


class Popup:
    def __init__(self, x, y, text, color=GOLD):
        self.x, self.y, self.text, self.color, self.life = x, y, text, color, 55

    def update(self):
        self.y -= 0.8
        self.life -= 1


class Coin:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.t = random.uniform(0, 100)

    def rect(self):
        bob = math.sin(self.t * 0.08) * 3
        return pygame.Rect(round(self.x - 9), round(self.y - 9 + bob), 18, 18)

    def draw(self, surf, cam):
        r = self.rect().move(-cam, 0)
        w = int(abs(math.cos(self.t * 0.08)) * 14) + 4
        body = pygame.Rect(0, 0, w, 18)
        body.center = r.center
        pygame.draw.ellipse(surf, GOLD_DARK, body)
        pygame.draw.ellipse(surf, GOLD, body.inflate(-4, -4))
        if w > 8:
            pygame.draw.line(surf, WHITE, (body.centerx - 1, body.top + 5), (body.centerx - 1, body.bottom - 6), 2)


# ------------------------------------------------------------------ player
class Player:
    W, H = 30, 42

    def __init__(self, x, y):
        self.x, self.y = float(x), float(y)
        self.w, self.h = self.W, self.H
        self.vx = self.vy = 0.0
        self.facing = 1
        self.on_ground = False
        self.hit_wall = False
        self.hearts = MAX_HEARTS
        self.invuln = 0
        self.knockback = 0
        self.attack_timer = 0
        self.cooldown = 0
        self.coyote = 0
        self.jump_buffer = 0
        self.anim = 0.0
        self.hit_ids = set()
        self.dead = False
        self.just_jumped = False
        self.just_swung = False

    def rect(self):
        return pygame.Rect(round(self.x), round(self.y), self.w, self.h)

    def attack_frame(self):
        return ATTACK_FRAMES - self.attack_timer if self.attack_timer else 0

    def attack_box(self):
        """The area the axe hurts this frame, or None. The axe is long!"""
        f = self.attack_frame()
        if not (ATTACK_ACTIVE[0] <= f <= ATTACK_ACTIVE[1]):
            return None
        r = self.rect()
        w, h = 92, 104
        x = r.centerx if self.facing > 0 else r.centerx - w
        return pygame.Rect(x, r.top - 48, w, h)

    def hurt(self, src_x):
        if self.invuln > 0 or self.dead:
            return False
        self.hearts -= 1
        self.invuln = INVULN_FRAMES
        self.knockback = 12
        self.vx = -6 if src_x > self.x + self.w / 2 else 6
        self.vy = -6
        return True

    def update(self, inp, level):
        self.just_jumped = self.just_swung = False
        if self.invuln > 0:
            self.invuln -= 1
        if self.cooldown > 0:
            self.cooldown -= 1

        # axe swing
        if inp.attack and self.attack_timer == 0 and self.cooldown == 0:
            self.attack_timer = ATTACK_FRAMES
            self.hit_ids.clear()
            self.just_swung = True
        if self.attack_timer > 0:
            self.attack_timer -= 1
            if self.attack_timer == 0:
                self.cooldown = ATTACK_COOLDOWN

        # running
        move = int(inp.right) - int(inp.left)
        if self.knockback > 0:
            self.knockback -= 1
            move = 0
        accel = RUN_ACCEL if self.on_ground else RUN_ACCEL * AIR_CONTROL
        top = MAX_RUN * (0.6 if self.attack_timer and self.on_ground else 1.0)
        if move:
            self.vx = max(-top, min(top, self.vx + move * accel))
            if self.attack_timer == 0:
                self.facing = move
        elif self.on_ground and self.knockback == 0:
            self.vx *= RUN_FRICTION
            if abs(self.vx) < 0.1:
                self.vx = 0

        # jumping
        self.coyote = COYOTE_FRAMES if self.on_ground else max(0, self.coyote - 1)
        self.jump_buffer = JUMP_BUFFER_FRAMES if inp.jump_pressed else max(0, self.jump_buffer - 1)
        if self.jump_buffer and self.coyote:
            self.vy = -JUMP_SPEED
            self.jump_buffer = self.coyote = 0
            self.on_ground = False
            self.just_jumped = True
        if not inp.jump_held and self.vy < -JUMP_CUT:
            self.vy = -JUMP_CUT

        physics_move(self, level)
        if self.x < 0:
            self.x, self.vx = 0, 0
        self.x = min(self.x, level.px_w - self.w)

        if self.on_ground and abs(self.vx) > 0.5:
            self.anim += abs(self.vx) * 0.25
        else:
            self.anim += 0.05


# ------------------------------------------------------------------ toads
class Toad:
    STATS = {   # size, hit points, hop strength, pause between hops, points
        "t": dict(w=32, h=24, hp=1, hop_vy=6.5, hop_vx=2.2, wait=(25, 55), score=100),
        "T": dict(w=46, h=40, hp=3, hop_vy=7.0, hop_vx=1.6, wait=(50, 80), score=500),
        "j": dict(w=28, h=22, hp=1, hop_vy=11.5, hop_vx=2.6, wait=(35, 60), score=150),
    }
    COLORS = {
        "t": [TOAD, TOAD_DARK, TOAD_BELLY],
        "T": [KING, KING_DARK, KING_BELLY],
        "j": [JUMPER, JUMPER_DARK, JUMPER_BELLY],
    }

    def __init__(self, kind, tx, ty):
        s = self.STATS[kind]
        self.kind = kind
        self.w, self.h = s["w"], s["h"]
        self.hp = self.max_hp = s["hp"]
        self.hop_vy, self.hop_vx = s["hop_vy"], s["hop_vx"]
        self.wait_range = s["wait"]
        self.score = s["score"]
        self.x = tx + (TILE - self.w) / 2
        self.y = ty + TILE - self.h
        self.vx = self.vy = 0.0
        self.dir = -1
        self.on_ground = False
        self.hit_wall = False
        self.wait = random.randint(10, 60)
        self.flash = 0
        self.stun = 0
        self.alive = True
        self.t = random.uniform(0, 100)

    def rect(self):
        return pygame.Rect(round(self.x), round(self.y), self.w, self.h)

    def colors(self):
        return self.COLORS[self.kind]

    def hit(self, from_dir):
        """Take one axe hit. Returns True if this killed the toad."""
        self.hp -= 1
        self.flash = 8
        self.stun = 16
        self.vx = from_dir * 6.5
        self.vy = -4
        self.dir = -from_dir
        if self.hp <= 0:
            self.alive = False
            return True
        return False

    def path_blocked(self, level):
        """Would the next hop run into a wall or off a ledge?"""
        r = self.rect()
        dist = self.hop_vx * 2 * self.hop_vy / GRAVITY
        front = r.right if self.dir > 0 else r.left
        near = int(front + self.dir * 4) // TILE
        land = int(front + self.dir * dist) // TILE
        below = (r.bottom + 2) // TILE
        if level.solid_at(near, (r.bottom - 4) // TILE):
            return True
        return not (level.solid_at(near, below) and level.solid_at(land, below))

    def update(self, level):
        self.t += 1
        if self.flash:
            self.flash -= 1
        if self.stun > 0:
            self.stun -= 1
            self.vx *= 0.9
        elif self.on_ground:
            self.vx = 0
            self.wait -= 1
            if self.wait <= 0:
                if self.path_blocked(level):
                    self.dir *= -1
                    self.wait = 12
                else:
                    self.vy = -self.hop_vy
                    self.vx = self.dir * self.hop_vx
                    self.wait = random.randint(*self.wait_range)
        physics_move(self, level)
        if self.hit_wall and self.stun == 0:
            self.dir *= -1
        if self.y > level.px_h + 100:
            self.alive = False


# ------------------------------------------------------------------ level
class Level:
    def __init__(self, rows):
        width = max(len(r) for r in rows)
        self.rows = [r.ljust(width, ".") for r in rows]
        self.w, self.h = width, len(self.rows)
        self.px_w, self.px_h = self.w * TILE, self.h * TILE
        self.tiles = {}
        self.coins = []
        self.enemies = []
        self.start = (TILE * 2, TILE * 9)
        self.flag = None
        for cy, row in enumerate(self.rows):
            for cx, ch in enumerate(row):
                x, y = cx * TILE, cy * TILE
                if ch in SOLID:
                    self.tiles[(cx, cy)] = ch
                elif ch == "o":
                    self.coins.append(Coin(x + TILE / 2, y + TILE / 2))
                elif ch == "P":
                    self.start = (x + (TILE - Player.W) / 2, y + TILE - Player.H)
                elif ch in Toad.STATS:
                    self.enemies.append(Toad(ch, x, y))
                elif ch == "F":
                    self.flag = pygame.Rect(x + TILE // 2 - 3, y + TILE - TILE * 7, 6, TILE * 7)

    def solid_at(self, cx, cy):
        return (cx, cy) in self.tiles

    def tiles_near(self, rect):
        x0 = max(rect.left // TILE - 1, 0)
        x1 = min(rect.right // TILE + 1, self.w - 1)
        y0 = max(rect.top // TILE - 1, 0)
        y1 = min(rect.bottom // TILE + 1, self.h - 1)
        for cy in range(y0, y1 + 1):
            for cx in range(x0, x1 + 1):
                if (cx, cy) in self.tiles:
                    yield (cx, cy), pygame.Rect(cx * TILE, cy * TILE, TILE, TILE)


# ------------------------------------------------------------------ drawing helpers
def make_tile_surfaces():
    rng = random.Random(7)

    def dirt():
        s = pygame.Surface((TILE, TILE))
        s.fill(DIRT)
        for _ in range(10):
            pygame.draw.rect(s, DIRT_DARK, (rng.randrange(TILE - 3), rng.randrange(TILE - 3), 3, 3))
        for _ in range(4):
            pygame.draw.rect(s, DIRT_LIGHT, (rng.randrange(TILE - 2), rng.randrange(TILE - 2), 2, 2))
        return s

    plain = dirt()
    grass = dirt()
    pygame.draw.rect(grass, GRASS_DARK, (0, 0, TILE, 13))
    pygame.draw.rect(grass, GRASS, (0, 0, TILE, 10))
    for x in range(3, TILE, 7):
        pygame.draw.line(grass, GRASS_LIGHT, (x, 2), (x + 2, 6), 2)
        pygame.draw.circle(grass, GRASS_DARK, (x + 2, 13), 3)

    stone = pygame.Surface((TILE, TILE))
    stone.fill(STONE)
    half = TILE // 2
    pygame.draw.line(stone, STONE_DARK, (0, half), (TILE, half), 2)
    pygame.draw.line(stone, STONE_DARK, (half, 0), (half, half), 2)
    pygame.draw.line(stone, STONE_DARK, (TILE // 4, half), (TILE // 4, TILE), 2)
    pygame.draw.line(stone, STONE_LIGHT, (3, 3), (half - 4, 3), 2)
    pygame.draw.line(stone, STONE_LIGHT, (half + 3, 3), (TILE - 4, 3), 2)
    pygame.draw.rect(stone, STONE_DARK, stone.get_rect(), 2)

    crate = pygame.Surface((TILE, TILE))
    crate.fill(WOOD)
    for y in (13, 26):
        pygame.draw.line(crate, WOOD_DARK, (0, y), (TILE, y), 2)
    pygame.draw.line(crate, WOOD_DARK, (4, 4), (TILE - 5, TILE - 5), 4)
    pygame.draw.rect(crate, WOOD_DARK, crate.get_rect(), 4)

    return {"grass": grass, "dirt": plain, "=": stone, "C": crate}


def axe_angle(p):
    """Axe angle in degrees: 0 = straight up, positive = towards the front."""
    if p.attack_timer == 0:
        bob = math.sin(p.anim * 1.4) * 4 if p.on_ground and abs(p.vx) > 0.5 else 0
        return -30 + bob
    return angle_at(p.attack_frame() / ATTACK_FRAMES)


def angle_at(prog):
    idle = -30
    if prog < 0.25:      # wind up over the shoulder
        return lerp(idle, -80, prog / 0.25)
    if prog < 0.6:       # big chop forwards
        return lerp(-80, 150, ease_out((prog - 0.25) / 0.35))
    return lerp(150, idle, (prog - 0.6) / 0.4)   # bring it back up


def draw_axe(spr, hand, d):
    n = (-d[1], d[0])                     # across the handle
    hx, hy = hand

    def pt(c, along, side):
        return (c[0] + d[0] * along + n[0] * side, c[1] + d[1] * along + n[1] * side)

    pygame.draw.line(spr, HANDLE_DARK, (hx - d[0] * 13, hy - d[1] * 13), (hx + d[0] * (AXE_LEN + 1), hy + d[1] * (AXE_LEN + 1)), 7)
    pygame.draw.line(spr, HANDLE, (hx - d[0] * 12, hy - d[1] * 12), (hx + d[0] * AXE_LEN, hy + d[1] * AXE_LEN), 4)
    for k in (18, 24, 30):   # leather wraps on the handle
        pygame.draw.line(spr, HANDLE_DARK, pt(hand, k, -3), pt(hand, k, 3), 2)
    c = (hx + d[0] * AXE_HEAD, hy + d[1] * AXE_HEAD)
    blade = [(6, 3), (17, 21), (6, 26), (-6, 26), (-17, 21), (-6, 3)]
    for s in (1, -1):   # two blades -> double axe
        pts = [pt(c, a, b * s) for a, b in blade]
        pygame.draw.polygon(spr, BLADE, pts)
        pygame.draw.polygon(spr, BLADE_DARK, pts, 2)
        pygame.draw.line(spr, WHITE, pt(c, 12, 21 * s), pt(c, -12, 21 * s), 2)
    pygame.draw.polygon(spr, BLADE_DARK, [pt(c, 5, -4), pt(c, 15, 0), pt(c, 5, 4)])
    pygame.draw.circle(spr, BLADE_DARK, (int(c[0]), int(c[1])), 5)


def draw_knight(surf, p, cam):
    size, bx, by = 210, 90, 90             # body box is drawn at (bx, by) inside the sprite
    spr = pygame.Surface((size, size), pygame.SRCALPHA)
    moving = p.on_ground and abs(p.vx) > 0.5
    step = math.sin(p.anim * 1.4) * 3 if moving else 0
    shoulder = (bx + 25, by + 18)
    rad = math.radians(axe_angle(p))
    d = (math.sin(rad), -math.cos(rad))
    hand = (shoulder[0] + d[0] * ARM_LEN, shoulder[1] + d[1] * ARM_LEN)

    # swing trail
    f = p.attack_frame()
    if ATTACK_ACTIVE[0] <= f <= ATTACK_ACTIVE[1]:
        prog = f / ATTACK_FRAMES
        reach = ARM_LEN + AXE_HEAD
        for k in range(1, 7):
            a = math.radians(angle_at(max(0.0, prog - k * 0.025)))
            pos = (shoulder[0] + math.sin(a) * reach, shoulder[1] - math.cos(a) * reach)
            pygame.draw.circle(spr, (255, 255, 255, max(0, 160 - k * 24)), (int(pos[0]), int(pos[1])), 16 - k * 2)

    # back arm: huge bare bicep, bracer and fist
    sw = -step * 0.8
    pygame.draw.ellipse(spr, SKIN_DARK, (bx - 12, by + 13, 16, 17))
    pygame.draw.ellipse(spr, SKIN, (bx - 11, by + 14, 14, 15))
    pygame.draw.circle(spr, SKIN_LIGHT, (bx - 6, by + 18), 2)
    pygame.draw.rect(spr, ARMOR_DARK, (bx - 10 + sw, by + 27, 11, 8), border_radius=3)
    pygame.draw.circle(spr, STEEL_DARK, (int(bx - 5 + sw), by + 37), 5)

    # thick legs
    if p.on_ground:
        legs = [(bx + 5 + step, by + 30), (bx + 16 - step, by + 30)]
    else:
        legs = [(bx + 3, by + 28), (bx + 18, by + 30)]
    for lx, ly in legs:
        pygame.draw.rect(spr, STEEL_DARK, (lx, ly, 10, 8), border_radius=3)
        pygame.draw.rect(spr, BOOT, (lx - 1, ly + 7, 13, 5), border_radius=2)

    # broad V-shaped torso with sculpted chest and abs
    torso = [(bx - 3, by + 13), (bx + 33, by + 13), (bx + 26, by + 31), (bx + 5, by + 31)]
    pygame.draw.polygon(spr, ARMOR, torso)
    pygame.draw.polygon(spr, ARMOR_DARK, torso, 2)
    for px in (bx + 3, bx + 15):
        pygame.draw.ellipse(spr, ARMOR_MID, (px, by + 14, 13, 9))
        pygame.draw.ellipse(spr, ARMOR_DARK, (px, by + 14, 13, 9), 1)
    for ax in (bx + 10, bx + 16):
        for ay in (by + 23, by + 26):
            pygame.draw.rect(spr, ARMOR_DARK, (ax, ay, 5, 3), 1, border_radius=1)
    pygame.draw.rect(spr, HANDLE_DARK, (bx + 6, by + 29, 20, 4))
    pygame.draw.rect(spr, GOLD, (bx + 17, by + 29, 5, 4))

    # thick neck and a (comparatively) small helmet with plume
    pygame.draw.rect(spr, STEEL_DARK, (bx + 11, by + 10, 13, 5))
    pb = step * 0.6
    pygame.draw.polygon(spr, PLUME, [(bx + 13, by - 1), (bx + 7, by - 10 + pb),
                                     (bx - 3, by - 6 + pb), (bx + 1, by), (bx + 9, by + 2)])
    helm = pygame.Rect(bx + 10, by - 3, 16, 15)
    pygame.draw.rect(spr, ARMOR, helm, border_radius=6)
    pygame.draw.rect(spr, ARMOR_DARK, helm, 2, border_radius=6)
    pygame.draw.line(spr, ARMOR_LIGHT, (bx + 13, by), (bx + 17, by), 2)
    pygame.draw.rect(spr, VISOR, (bx + 18, by + 2, 8, 3))
    pygame.draw.rect(spr, (255, 240, 150), (bx + 22, by + 3, 2, 2))

    # back shoulder plate
    pygame.draw.circle(spr, ARMOR_LIGHT, (bx + 1, by + 14), 6)
    pygame.draw.circle(spr, ARMOR_DARK, (bx + 1, by + 14), 6, 2)

    # the axe, then the front arm gripping it
    draw_axe(spr, hand, d)
    pygame.draw.line(spr, SKIN_DARK, shoulder, hand, 13)
    pygame.draw.line(spr, SKIN, shoulder, hand, 10)
    bicep = (int(shoulder[0] + d[0] * 8), int(shoulder[1] + d[1] * 8))
    pygame.draw.circle(spr, SKIN_DARK, bicep, 9)
    pygame.draw.circle(spr, SKIN, bicep, 8)
    pygame.draw.circle(spr, SKIN_LIGHT, (bicep[0] - 2, bicep[1] - 2), 2)
    pygame.draw.circle(spr, ARMOR_DARK, (int(hand[0]), int(hand[1])), 6)
    pygame.draw.circle(spr, STEEL, (int(hand[0]), int(hand[1])), 3)

    # big front shoulder plate with a gold rivet
    pygame.draw.circle(spr, ARMOR_LIGHT, (bx + 27, by + 15), 6)
    pygame.draw.circle(spr, ARMOR_DARK, (bx + 27, by + 15), 6, 2)
    pygame.draw.circle(spr, GOLD, (bx + 27, by + 15), 2)

    if p.facing < 0:
        spr = pygame.transform.flip(spr, True, False)
    ox = bx if p.facing > 0 else size - bx - p.w
    surf.blit(spr, (round(p.x) - ox - cam, round(p.y) - by))


def draw_toad(surf, e, cam):
    w, h, pad = e.w, e.h, 16
    spr = pygame.Surface((w + pad * 2, h + pad * 2), pygame.SRCALPHA)
    main, dark, belly = e.colors()
    if e.flash:
        main, dark, belly = WHITE, (210, 210, 210), WHITE
    ox, oy = pad, pad

    # back leg: folded when sitting, stretched out when hopping
    if e.on_ground:
        pygame.draw.ellipse(spr, dark, (ox - 2, oy + h * 0.5, w * 0.5, h * 0.5))
        pygame.draw.ellipse(spr, dark, (ox - 5, oy + h - 5, w * 0.45, 5))
    else:
        pygame.draw.line(spr, dark, (ox + w * 0.3, oy + h * 0.75), (ox - w * 0.25, oy + h + 4), max(4, w // 7))
        pygame.draw.ellipse(spr, dark, (ox - w * 0.4, oy + h + 1, w * 0.3, 5))

    if e.kind == "T":   # the king toad wears a crown
        cx, base = ox + w * 0.32, oy + h * 0.22
        crown = [(cx - 9, base + 2), (cx - 9, base - 8), (cx - 4, base - 4), (cx, base - 11),
                 (cx + 4, base - 4), (cx + 9, base - 8), (cx + 9, base + 2)]
        pygame.draw.polygon(spr, GOLD, crown)
        pygame.draw.polygon(spr, GOLD_DARK, crown, 2)

    body = pygame.Rect(ox, oy + int(h * 0.2), w, h - int(h * 0.2))
    pygame.draw.ellipse(spr, main, body)
    pygame.draw.ellipse(spr, dark, body, 2)
    pygame.draw.ellipse(spr, belly, (ox + w * 0.38, oy + h * 0.55, w * 0.58, h * 0.42))
    wart = max(2, w // 14)
    for fx, fy in ((0.16, 0.48), (0.34, 0.36), (0.26, 0.64), (0.5, 0.44)):
        pygame.draw.circle(spr, BLACK if e.kind == "j" else dark, (ox + w * fx, oy + h * fy), wart)

    # bulging eyes with horizontal pupils
    er = max(4, int(w * 0.13))
    for fx in (0.55, 0.8):
        cx, cy = ox + w * fx, oy + h * 0.24
        pygame.draw.circle(spr, main, (cx, cy), er + 2)
        pygame.draw.circle(spr, TOAD_EYE, (cx, cy), er)
        pygame.draw.rect(spr, BLACK, (cx - er * 0.7, cy - 1, er * 1.4, 3))

    pygame.draw.line(spr, dark, (ox + w * 0.6, oy + h * 0.6), (ox + w - 1, oy + h * 0.52), 2)
    if e.on_ground and math.sin(e.t * 0.07) > 0.85:   # croaking throat
        pygame.draw.circle(spr, (245, 200, 180), (ox + w * 0.8, oy + h * 0.72), max(4, w * 0.16))
    pygame.draw.rect(spr, dark, (ox + w * 0.7, oy + h * 0.82, max(4, w // 8), h * 0.2))

    if e.dir < 0:
        spr = pygame.transform.flip(spr, True, False)
    r = e.rect()
    surf.blit(spr, (r.x - pad - cam, r.y - pad))
    if e.max_hp > 1:   # health pips
        for i in range(e.max_hp):
            col = HEART if i < e.hp else HEART_EMPTY
            pygame.draw.rect(surf, col, (r.centerx - cam - 14 + i * 10, r.y - 22, 8, 5))


def draw_heart(surf, x, y, full):
    col = HEART if full else HEART_EMPTY
    pygame.draw.circle(surf, col, (x + 5, y + 5), 5)
    pygame.draw.circle(surf, col, (x + 13, y + 5), 5)
    pygame.draw.polygon(surf, col, [(x, y + 7), (x + 18, y + 7), (x + 9, y + 17)])


def draw_cloud(surf, x, y, s):
    for dx, dy, rad in ((0, 0, 22), (25, -10, 28), (55, 0, 22), (28, 6, 22)):
        pygame.draw.circle(surf, WHITE, (int(x + dx * s), int(y + dy * s)), int(rad * s))


# ------------------------------------------------------------------ game
class Input:
    def __init__(self):
        self.left = self.right = self.jump_held = False
        self.jump_pressed = self.attack = False


class Game:
    def __init__(self, screen):
        self.screen = screen
        self.canvas = pygame.Surface((SCREEN_W, SCREEN_H))
        self.font_big = pygame.font.Font(None, 96)
        self.font_mid = pygame.font.Font(None, 40)
        self.font_small = pygame.font.Font(None, 28)
        self.tile_imgs = make_tile_surfaces()
        self.sky = pygame.Surface((SCREEN_W, SCREEN_H))
        for y in range(SCREEN_H):
            t = y / SCREEN_H
            col = tuple(int(lerp(a, b, t)) for a, b in zip(SKY_TOP, SKY_BOTTOM))
            pygame.draw.line(self.sky, col, (0, y), (SCREEN_W, y))
        rng = random.Random(3)
        self.clouds = [(rng.uniform(0, SCREEN_W + 300), rng.uniform(40, 170), rng.uniform(0.7, 1.3))
                       for _ in range(7)]
        self.sound = SoundBank()
        self.inp = Input()
        self.t = 0
        self.state = "title"
        self.state_timer = 0
        self.lives, self.score, self.coins = START_LIVES, 0, 0
        self.reset_level()

    # ---- state changes
    def new_game(self):
        self.lives, self.score, self.coins = START_LIVES, 0, 0
        self.reset_level()
        self.state = "play"
        self.sound.say("vamos", force=True)

    def reset_level(self):
        self.level = Level(LEVEL_MAP)
        self.player = Player(*self.level.start)
        self.particles = []
        self.popups = []
        self.cam_x = 0.0
        self.shake = 0

    def lose_life(self):
        self.lives -= 1
        self.state = "dying"
        self.state_timer = 110
        p = self.player
        p.dead = True
        p.vy = -11
        p.attack_timer = 0
        p.invuln = 0
        self.sound.play("die")
        if self.lives > 0:
            self.sound.say("desastre", force=True)

    def handle_event(self, e):
        if e.type != pygame.KEYDOWN:
            return
        if e.key in JUMP_KEYS:
            self.inp.jump_pressed = True
        if e.key in ATTACK_KEYS:
            self.inp.attack = True
        if e.key == pygame.K_m:
            self.sound.toggle()
        if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and self.state in ("title", "gameover", "win"):
            self.new_game()

    # ---- effects
    def burst(self, x, y, colors, n, speed=4.0):
        for _ in range(n):
            a = random.uniform(0, math.tau)
            v = random.uniform(1, speed)
            self.particles.append(Particle(x, y, math.cos(a) * v, math.sin(a) * v - 2,
                                           random.choice(colors), random.randint(20, 40), random.randint(3, 6)))

    def popup(self, x, y, text, color=GOLD):
        self.popups.append(Popup(x, y, text, color))

    # ---- update
    def step(self):
        self.t += 1
        if self.state == "play":
            self.update_play()
        elif self.state == "dying":
            p = self.player
            p.vy = min(p.vy + GRAVITY * 0.8, MAX_FALL)
            p.y += p.vy
            self.state_timer -= 1
            if self.state_timer <= 0:
                if self.lives > 0:
                    self.reset_level()
                    self.state = "play"
                else:
                    self.state = "gameover"
                    self.sound.play("gameover")
                    self.sound.say("fin", force=True)
        elif self.state == "win":
            self.state_timer += 1
            if self.state_timer % 18 == 0:
                x = self.cam_x + random.uniform(100, SCREEN_W - 100)
                cols = random.choice([[GOLD, WHITE], [HEART, WHITE], [ARMOR_LIGHT, WHITE], [GRASS_LIGHT, WHITE]])
                self.burst(x, random.uniform(60, 220), cols, 30, 6)

        for c in self.level.coins:
            c.t += 1
        for part in self.particles:
            part.update()
        self.particles = [q for q in self.particles if q.life > 0]
        for pop in self.popups:
            pop.update()
        self.popups = [q for q in self.popups if q.life > 0]
        if self.shake > 0:
            self.shake -= 1
        self.inp.jump_pressed = self.inp.attack = False

    def update_play(self):
        p, lvl, snd = self.player, self.level, self.sound
        p.update(self.inp, lvl)
        if p.just_jumped:
            snd.play("jump")
        if p.just_swung:
            snd.play("swing")

        # the axe hits toads and crates
        box = p.attack_box()
        if box:
            for e in lvl.enemies:
                if e.alive and id(e) not in p.hit_ids and box.colliderect(e.rect()):
                    p.hit_ids.add(id(e))
                    er = e.rect()
                    self.burst(er.centerx, er.centery, [WHITE, (255, 230, 120)], 8)
                    self.shake = max(self.shake, 5)
                    snd.play("hit")
                    if e.hit(p.facing):
                        self.score += e.score
                        word = "¡Adiós, rey!" if e.kind == "T" else random.choice(["¡Toma!", "¡Zas!", "¡Adiós!"])
                        self.popup(er.centerx, er.top - 10, f"{word} +{e.score}")
                        self.burst(er.centerx, er.centery, e.colors(), 20, 5)
                        if e.kind == "T":
                            snd.play("croak_big")
                            snd.say("rey", force=True)
                        else:
                            snd.play("croak")
                            snd.say(random.choice(["toma", "adios"]))
            for key, tr in list(lvl.tiles_near(box)):
                if lvl.tiles.get(key) == "C" and box.colliderect(tr):
                    del lvl.tiles[key]
                    self.burst(tr.centerx, tr.centery, [WOOD, WOOD_DARK], 14)
                    lvl.coins.append(Coin(tr.centerx, tr.centery))
                    self.score += 10
                    self.shake = max(self.shake, 3)
                    self.popup(tr.centerx, tr.top, "¡Crac!", WHITE)
                    snd.play("crate")

        for e in lvl.enemies:
            e.update(lvl)
        lvl.enemies = [e for e in lvl.enemies if e.alive]

        # touching a toad hurts (even from above - you have to chop them!)
        pr = p.rect().inflate(-6, -4)
        for e in lvl.enemies:
            if e.stun == 0 and pr.colliderect(e.rect()):
                if p.hurt(e.rect().centerx):
                    self.shake = 8
                    self.burst(pr.centerx, pr.centery, [HEART, WHITE], 10)
                    self.popup(pr.centerx, pr.top - 10, "¡Ay!", HEART)
                    snd.play("hurt")
                    snd.say("ay", force=True)

        for c in lvl.coins[:]:
            if pr.colliderect(c.rect()):
                lvl.coins.remove(c)
                self.coins += 1
                self.score += 50
                self.burst(c.x, c.y, [GOLD, WHITE], 6, 3)
                snd.play("coin")
                if self.coins % 5 == 0:
                    snd.say("oro")

        if lvl.flag and p.rect().colliderect(lvl.flag.inflate(20, 0)):
            bonus = 1000 + 250 * p.hearts
            self.score += bonus
            self.popup(p.rect().centerx, p.rect().top - 10, f"¡Olé! +{bonus}")
            self.state = "win"
            self.state_timer = 0
            snd.play("win")
            snd.say("ole", force=True)
            return

        if p.hearts <= 0 or p.y > lvl.px_h + 60:
            self.lose_life()
            return

        target = p.x + p.w / 2 - SCREEN_W * 0.42
        self.cam_x += (target - self.cam_x) * 0.12
        self.cam_x = max(0.0, min(self.cam_x, lvl.px_w - SCREEN_W))

    # ---- drawing
    def text(self, surf, msg, font, center=None, topleft=None, color=WHITE):
        img = font.render(msg, True, color)
        shadow = font.render(msg, True, BLACK)
        r = img.get_rect()
        if center:
            r.center = center
        else:
            r.topleft = topleft
        surf.blit(shadow, r.move(2, 2))
        surf.blit(img, r)

    def draw_hills(self, surf, offset, top, height, color, period):
        x = -int(offset % period) - period
        while x < SCREEN_W + period:
            pygame.draw.ellipse(surf, color, (x, top, int(period * 1.2), height * 2))
            x += period

    def draw_background(self, surf, cam):
        surf.blit(self.sky, (0, 0))
        pygame.draw.circle(surf, (255, 244, 180), (SCREEN_W - 140, 90), 42)
        for cx, cy, s in self.clouds:
            x = (cx - cam * 0.15) % (SCREEN_W + 300) - 150
            draw_cloud(surf, x, cy, s)
        self.draw_hills(surf, cam * 0.25, 300, 220, HILL_FAR, 420)
        self.draw_hills(surf, cam * 0.5, 370, 160, HILL_NEAR, 300)

    def draw_tiles(self, surf, cam):
        lvl = self.level
        for cx in range(cam // TILE, (cam + SCREEN_W) // TILE + 2):
            for cy in range(lvl.h):
                ch = lvl.tiles.get((cx, cy))
                if not ch:
                    continue
                if ch == "#":
                    img = self.tile_imgs["dirt" if lvl.solid_at(cx, cy - 1) else "grass"]
                else:
                    img = self.tile_imgs[ch]
                surf.blit(img, (cx * TILE - cam, cy * TILE))

    def draw_flag(self, surf, cam):
        f = self.level.flag
        if not f:
            return
        x = f.centerx - cam
        pygame.draw.line(surf, STONE_DARK, (x, f.top), (x, f.bottom), 5)
        pygame.draw.line(surf, STONE_LIGHT, (x - 1, f.top), (x - 1, f.bottom), 1)
        pygame.draw.circle(surf, GOLD, (x, f.top), 7)
        wave = math.sin(self.t * 0.1) * 4
        banner = [(x + 2, f.top + 8), (x + 46, f.top + 22 + wave), (x + 2, f.top + 36)]
        pygame.draw.polygon(surf, ARMOR, banner)
        pygame.draw.polygon(surf, ARMOR_DARK, banner, 2)

    def draw_hud(self, surf):
        p = self.player
        for i in range(MAX_HEARTS):
            draw_heart(surf, 16 + i * 24, 14, i < p.hearts)
        self.text(surf, f"VIDAS {self.lives}", self.font_small, topleft=(16, 40))
        self.text(surf, f"MONEDAS {self.coins}", self.font_small, topleft=(SCREEN_W // 2 - 60, 14))
        self.text(surf, f"PUNTOS {self.score:06d}", self.font_small, topleft=(SCREEN_W - 200, 14))
        if not self.sound.enabled:
            self.text(surf, "SONIDO: NO (M)", self.font_small, topleft=(SCREEN_W - 200, 40))

    def overlay(self, surf, lines):
        shade = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        shade.fill((10, 15, 40, 140))
        surf.blit(shade, (0, 0))
        for msg, font, y, color in lines:
            self.text(surf, msg, font, center=(SCREEN_W // 2, y), color=color)

    def draw(self):
        surf = self.canvas
        cam = int(self.cam_x)
        self.draw_background(surf, cam)
        self.draw_tiles(surf, cam)
        self.draw_flag(surf, cam)
        for c in self.level.coins:
            c.draw(surf, cam)
        for e in self.level.enemies:
            draw_toad(surf, e, cam)
        p = self.player
        if not (p.invuln > 0 and (p.invuln // 4) % 2 == 0):
            draw_knight(surf, p, cam)
        for part in self.particles:
            part.draw(surf, cam)
        for pop in self.popups:
            self.text(surf, pop.text, self.font_small, center=(int(pop.x - cam), int(pop.y)), color=pop.color)

        if self.state != "title":
            self.draw_hud(surf)
        blink = (self.t // 30) % 2 == 0
        if self.state == "title":
            self.overlay(surf, [
                ("EL CABALLERO DEL HACHA", self.font_big, 120, ARMOR_LIGHT),
                ("¡Abre camino a hachazos hasta la bandera!", self.font_mid, 190, WHITE),
                ("Mover: Flechas / A D      Saltar: Espacio / W", self.font_small, 260, WHITE),
                ("Hachazo: X / J      Sonido: M", self.font_small, 292, WHITE),
                ("¡Ojo! Saltar sobre los sapos duele.", self.font_small, 324, WHITE),
                ("Pulsa ENTER para empezar" if blink else "", self.font_mid, 400, GOLD),
            ])
        elif self.state == "dying" and self.lives > 0:
            self.text(surf, "¡Ay!", self.font_big, center=(SCREEN_W // 2, SCREEN_H // 2 - 40), color=HEART)
        elif self.state == "gameover":
            self.overlay(surf, [
                ("FIN DEL JUEGO", self.font_big, 170, HEART),
                (f"Puntos: {self.score}", self.font_mid, 250, WHITE),
                ("Pulsa ENTER para intentarlo otra vez" if blink else "", self.font_mid, 340, GOLD),
            ])
        elif self.state == "win" and self.state_timer > 40:
            self.overlay(surf, [
                ("¡OLÉ!", self.font_big, 140, GOLD),
                ("¡Misión cumplida, caballero!", self.font_mid, 210, WHITE),
                (f"Puntos: {self.score}      Monedas: {self.coins}", self.font_mid, 260, WHITE),
                ("Pulsa ENTER para jugar otra vez" if blink else "", self.font_mid, 350, GOLD),
            ])

        ox = oy = 0
        if self.shake:
            ox, oy = random.randint(-self.shake, self.shake), random.randint(-self.shake, self.shake)
        self.screen.fill(BLACK)
        self.screen.blit(surf, (ox, oy))


LEFT_KEYS = (pygame.K_LEFT, pygame.K_a)
RIGHT_KEYS = (pygame.K_RIGHT, pygame.K_d)
JUMP_KEYS = (pygame.K_SPACE, pygame.K_UP, pygame.K_w)
ATTACK_KEYS = (pygame.K_x, pygame.K_j, pygame.K_LCTRL)


def main():
    prepare_voices()
    pygame.mixer.pre_init(AUDIO_RATE, -16, 2, 512)
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("El Caballero del Hacha")
    clock = pygame.time.Clock()
    game = Game(screen)
    while True:
        for e in pygame.event.get():
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                pygame.quit()
                sys.exit()
            game.handle_event(e)
        keys = pygame.key.get_pressed()
        game.inp.left = any(keys[k] for k in LEFT_KEYS)
        game.inp.right = any(keys[k] for k in RIGHT_KEYS)
        game.inp.jump_held = any(keys[k] for k in JUMP_KEYS)
        game.step()
        game.draw()
        pygame.display.flip()
        clock.tick(FPS)


if __name__ == "__main__":
    main()
