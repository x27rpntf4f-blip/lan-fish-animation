import random
import math
import colorsys


class Fish:
    _id_counter = 0

    def __init__(self, host_id, x=None, y=None):
        self.fish_id = (host_id << 8) | (Fish._id_counter & 0xFF)
        Fish._id_counter += 1

        self.x = x if x is not None else random.uniform(100, 700)
        self.y = y if y is not None else random.uniform(100, 500)
        self.direction = random.uniform(0, 2 * math.pi)
        self.speed = random.uniform(60, 160)
        self.size = random.uniform(0.6, 1.4)
        self.color = self._random_color()
        self.host_id = host_id
        self.wag_phase = random.uniform(0, 2 * math.pi)
        self.transfer_cooldown = 0.0

    def _random_color(self):
        h = random.random()
        s = random.uniform(0.6, 0.9)
        v = random.uniform(0.7, 1.0)
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        return (int(r * 255), int(g * 255), int(b * 255))

    def update(self, dt, speed_multiplier=1.0):
        effective_speed = self.speed * speed_multiplier
        self.x += math.cos(self.direction) * effective_speed * dt
        self.y += math.sin(self.direction) * effective_speed * dt
        self.wag_phase += effective_speed * dt * 0.06

    def bounce(self, screen_w, screen_h, margin=20):
        bounced = False
        if self.x < margin:
            self.x = margin
            self.direction = math.pi - self.direction
            bounced = True
        elif self.x > screen_w - margin:
            self.x = screen_w - margin
            self.direction = math.pi - self.direction
            bounced = True
        if self.y < margin:
            self.y = margin
            self.direction = -self.direction
            bounced = True
        elif self.y > screen_h - margin:
            self.y = screen_h - margin
            self.direction = -self.direction
            bounced = True
        if bounced:
            self.direction += random.uniform(-0.3, 0.3)
        return bounced
