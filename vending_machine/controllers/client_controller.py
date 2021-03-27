import os
from queue import Queue
from .cash_controller import CashController
from .nfc_controller import NFCTag, NFCController
from .ec_card_controller import ECCardController
from .api_controller import APIController
from .frontend_controller import FrontendController
from ..status_light import StatusLight
from ..main_power_switch import MainPowerSwitch
from gpiozero.pins.mock import MockFactory
from gpiozero import Device
from time import sleep
from threading import Thread
from .client_context import ClientContext

if os.environ.get('TESTING_ENVIRONMENT', None):
    Device.pin_factory = MockFactory()


class ClientController(Thread):
    def __init__(self, context: ClientContext):
        self.signals = Queue()
        self.context = context

        self.cash_controller = CashController(report_to=self.signals)
        self.nfc_controller = NFCController(report_to=self.signals)
        self.ec_card_controller = ECCardController(report_to=self.signals)
        self.frontend_controller = FrontendController(report_to=self.signals)
        self.api_controller = APIController(report_to=self.signals, context=self.context)

        self.status_light = StatusLight()
        self.power_switch = MainPowerSwitch()

        super(ClientController, self).__init__(target=self.handler)

    def handler(self):
        pass

    def start_all(self):
        self.api_controller.start_all()
        self.cash_controller.start_all()
        self.nfc_controller.start_all()
        self.frontend_controller.start_all()
        self.ec_card_controller.start_all()

        sleep(1)
        self.power_switch.power_on()

    def shutdown(self):
        pass
