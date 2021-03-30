from .pins import Pins
from gpiozero import OutputDevice


class StatusLight:
    def __init__(self):
        self._relay = OutputDevice(Pins.STATUS_LIGHT_RELAY)
        self._is_red, self._is_green = None, None
        self.red()

    @property
    def is_red(self):
        return self._is_red

    @property
    def is_green(self):
        return self._is_green

    def red(self):
        self._relay.on()
        self._is_red = True
        self._is_green = False

    def green(self):
        self._relay.off()
        self._is_red = False
        self._is_green = True
