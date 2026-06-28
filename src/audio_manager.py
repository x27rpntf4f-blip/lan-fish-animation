import os
import pygame


class AudioManager:
    def __init__(self, volume=0.5):
        self.enabled = False
        self.volume = volume

        if not pygame.mixer.get_init():
            try:
                pygame.mixer.init()
            except pygame.error:
                return

        path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                            "assets", "water.wav")
        if not os.path.exists(path):
            return

        try:
            self.sound = pygame.mixer.Sound(path)
            self.sound.set_volume(volume)
            self.channel = None
            self.enabled = True
        except pygame.error:
            pass

    def play(self):
        if self.enabled:
            self.channel = self.sound.play(-1)

    def toggle(self):
        if not self.enabled or self.channel is None:
            return
        if self.channel.get_busy():
            self.channel.pause()
        else:
            self.channel.unpause()

    def set_volume(self, v):
        self.volume = v
        if self.enabled:
            self.sound.set_volume(v)

    def stop(self):
        if self.enabled and self.channel:
            self.channel.stop()
