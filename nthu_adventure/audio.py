"""Original score loops and synthetic, non-verbal effects."""
from array import array
import math

import pygame

from .constants import ROOT

SCORE_RMS = 0.11
SCORE_PEAK = 0.78
PCM_SCALE = 32768


def load_loop(path, *, score):
    sound = pygame.mixer.Sound(path)
    if not score or pygame.mixer.get_init()[1] != -16:
        return sound
    samples = array("h", sound.get_raw())
    if not samples:
        return sound
    peak = max(map(abs, samples))
    if not peak:
        return sound
    rms = math.sqrt(sum(sample * sample for sample in samples) / len(samples))
    # Match the quiet score files before applying the scene crossfade.
    gain = min(SCORE_RMS * PCM_SCALE / rms, SCORE_PEAK * PCM_SCALE / peak)
    return pygame.mixer.Sound(buffer=array("h", (round(sample * gain) for sample in samples)))


class AudioManager:
    def __init__(self):
        self.sounds = {}
        self.tracks = {}
        self.channels = {}
        self.levels = {}
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)
            frequency, _, channels = pygame.mixer.get_init()
            for key, freq, duration in (
                ("select", 440, .055), ("photo", 780, .10), ("quest", 520, .24),
                ("warning", 315, .12), ("call", 125, .48), ("bat", 95, .11), ("power", 63, .33), ("scare", 77, .32),
            ):
                samples = array("h")
                for i in range(round(frequency * duration)):
                    t = i / frequency
                    envelope = min(1, i / 140) * (1 - t / duration)
                    signal = math.sin(math.tau * (freq + 25 * math.sin(t * 17)) * t)
                    samples.extend([round(signal * envelope * 2600)] * channels)
                self.sounds[key] = pygame.mixer.Sound(buffer=samples)
            names = ("dusk", "night", "pursuit", "arrival", "rain")
            pygame.mixer.set_reserved(len(names))
            for index, name in enumerate(names):
                path = ROOT / "assets" / "score" / f"{name}.wav"
                try:
                    self.tracks[name] = load_loop(path, score=name != "rain")
                except (OSError, pygame.error):
                    continue
                self.channels[name] = pygame.mixer.Channel(index)
                self.levels[name] = 0.
        except pygame.error:
            pass

    def play(self, key):
        if key in self.sounds and pygame.mixer.get_init():
            self.sounds[key].play()

    def mix(self, cue, raining, dt):
        """Keep continuous loops running and crossfade their levels."""
        if not self.channels or not pygame.mixer.get_init():
            return
        if cue and cue not in self.channels:
            cue = next((name for name in self.channels if name != "rain"), None)
        blend = min(1., max(0., dt) * 3.5)
        for name, channel in self.channels.items():
            target = .28 if name == "rain" and raining else .62 if name == cue else 0.
            if not channel.get_busy():
                channel.set_volume(0.)
                channel.play(self.tracks[name], loops=-1)
            level = self.levels[name] + (target - self.levels[name]) * blend
            self.levels[name] = level
            channel.set_volume(level)

    def close(self):
        if pygame.mixer.get_init():
            for channel in self.channels.values():
                channel.stop()
