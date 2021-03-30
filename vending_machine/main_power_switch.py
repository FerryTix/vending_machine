from .pins import Pins
from gpiozero import OutputDevice


class MainPowerSwitch:
    def __init__(self):
        self._relay = OutputDevice(Pins.MAIN_POWER_RELAY)
        self._power_is_on = None
        self.power_off()

    @property
    def power_is_on(self):
        return self._power_is_on

    def power_off(self):
        self._relay.on()
        self._power_is_on = False

    def power_on(self):
        self._relay.off()
        self._power_is_on = True
