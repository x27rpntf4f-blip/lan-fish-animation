import importlib.resources
import logging

import pygame

logger = logging.getLogger(__name__)


class AudioManager:
    def __init__(self, volume=0.5):
        self.enabled = False
        self.volume = volume
        self.channel = None

        if not pygame.mixer.get_init():
            try:
                pygame.mixer.init()
            except pygame.error as exc:
                logger.warning(
                    "Audio mixer initialization failed",
                    extra={"event": "audio_unavailable", "audio_enabled": False, "error": str(exc)},
                )
                return

        try:
            resource = importlib.resources.files("fish_demo.resources").joinpath("water.wav")
            with importlib.resources.as_file(resource) as path:
                self.sound = pygame.mixer.Sound(str(path))
            self.sound.set_volume(volume)
            self.enabled = True
            logger.info(
                "Audio initialized",
                extra={
                    "event": "audio_ready",
                    "audio_enabled": True,
                    "resource_name": "water.wav",
                },
            )
        except (FileNotFoundError, ModuleNotFoundError, pygame.error) as exc:
            logger.warning(
                "Audio resource unavailable",
                extra={"event": "audio_unavailable", "audio_enabled": False, "error": str(exc)},
            )

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
