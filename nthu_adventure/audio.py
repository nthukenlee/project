"""Original quiet synthesized UI and speech-like vocal cues."""
import math
from array import array
import pygame

class AudioManager:
    def __init__(self):
        self.sounds={}
        try:
            pygame.mixer.init(frequency=22050,size=-16,channels=1,buffer=512)
            for key,freq,duration in [('select',440,.055),('photo',780,.10),('quest',520,.24),('voice',175,.22)]:
                samples=array('h')
                for i in range(round(22050*duration)):
                    t=i/22050; envelope=min(1,i/140)*(1-t/duration)
                    signal=math.sin(math.tau*(freq+25*math.sin(t*17))*t)
                    samples.append(round(signal*envelope*2600))
                self.sounds[key]=pygame.mixer.Sound(buffer=samples)
        except pygame.error: pass
    def play(self,key):
        if key in self.sounds: self.sounds[key].play()
