from changebox import ChangeBox
from enum import Enum
from datetime import datetime
from threading import Lock, Thread, RLock
from gpiozero.pins.mock import MockFactory
from gpiozero import Device, Button, OutputDevice
from ..pins import Pins
import os
from client_constants import CashControllerCommand, CashControllerMessage
from queue import Empty, Queue, Full

# Set the default pin factory to a mock factory, if in testing environment
if os.environ.get('TESTING_ENVIRONMENT', None):
    Device.pin_factory = MockFactory()


class Status(Enum):
    ACCEPTING_CASH = 1
    DENYING_CASH = 2
    PAYMENT_READY = 4


class CashState:
    def __init__(self):
        self.BALANCE_LOCK = Lock()
        self._balance = 0
        self.required_amount = 0
        self.status: Status = Status.DENYING_CASH

    @property
    def balance(self):
        return self._balance

    @balance.setter
    def balance(self, balance):
        self._balance = balance


class CollectorPosition(Enum):
    DROP = "DROP"
    TAKE = "TAKE"
    COLLECT = "COLLECT"


class CashController(Thread):
    def __init__(self, report_to: Queue, *args, **kwargs):
        self.results = report_to
        self.change_box = ChangeBox()
        self.last_reported_amount = None
        self.last_command = None

        self.note_register = NoteAcceptorRegister(self)
        self.coin_register = CoinAcceptorRegister(self)

        self.cash_state = CashState()
        self.tasks = Queue()

        super().__init__(target=self.handler)

    def not_registering(self):
        with self.coin_register.last_pulse_l, self.note_register.last_pulse_l:
            return (
                    (
                            not self.coin_register.last_pulse or
                            (datetime.now() - self.coin_register.last_pulse).seconds >= 1
                    )
                    and (
                            not self.note_register.last_pulse or
                            (datetime.now() - self.note_register.last_pulse).seconds >= 2
                    )
            )

    def handler(self):
        while True:
            functions = {
                CashControllerCommand.ACCEPT_CASH:
                    self.enable_cash if self.cash_state.status == Status.DENYING_CASH else
                    self.update_payment_status if self.cash_state.status == Status.ACCEPTING_CASH else None,
                CashControllerCommand.DENY_CASH:
                    self.cancel_cash if self.cash_state.status == Status.ACCEPTING_CASH else
                    self.cancel_cash if self.cash_state.status == Status.PAYMENT_READY else None,
                CashControllerCommand.TAKE_MONEY:
                    self.collect_payment if self.cash_state.status == Status.PAYMENT_READY else None,
            }

            try:
                cmd = self.tasks.get(timeout=1 if self.last_command else None)
                cmd = cmd.decode("utf-8")
                command = (
                    CashControllerCommand.ACCEPT_CASH if cmd.startswith(CashControllerCommand.ACCEPT_CASH.value)
                    else CashControllerCommand.DENY_CASH if cmd.startswith(
                        CashControllerCommand.DENY_CASH.value) else
                    CashControllerCommand.TAKE_MONEY if cmd.startswith(
                        CashControllerCommand.TAKE_MONEY.value) else None
                )
                if command:
                    fun = functions[command]
                    if fun:
                        if fun(command=cmd):
                            self.last_command = None
                        else:
                            self.last_command = (command, cmd)

            except Empty as e:
                if self.last_command:
                    fun = functions[self.last_command[0]]
                    if fun(command=None):
                        self.last_command = None

    # Payment Ready, Command Take Money
    def collect_payment(self, command=None):
        self.set_collector(CollectorPosition.TAKE)

        assert not self.coin_register.is_open
        assert not self.note_register.is_open

        if self.not_registering():
            with self.cash_state.BALANCE_LOCK:
                if self.cash_state.required_amount < self.cash_state.balance:
                    self.change_box.give_change(self.cash_state.balance - self.cash_state.required_amount)

            self.reset_cash_state()
            self.results.put(CashControllerMessage.PAYMENT_COLLECTED.value)
            return True
        return False

    def set_collector(self, position):
        pass

    # Payment Ready, Command deny Cash
    def drop_payment(self, command=None):
        if self.coin_register.is_open or self.note_register.is_open:
            raise RuntimeError()

        self.set_collector(CollectorPosition.DROP)
        self.reset_cash_state()

        self.results.put(CashControllerMessage.PAYMENT_DROPPED.value)

        return True

    def reset_cash_state(self):
        with self.cash_state.BALANCE_LOCK:
            self.cash_state.balance = 0
            self.cash_state.required_amount = 0
            self.cash_state.status = Status.DENYING_CASH
            self.last_reported_amount = 0
        return True

    # Denying Cash, Command accept cash
    def enable_cash(self, command=None):
        assert not self.coin_register.is_open
        assert not self.note_register.is_open
        assert self.cash_state.status == Status.DENYING_CASH

        if self.not_registering():
            with self.cash_state.BALANCE_LOCK:
                required_amount = int(command.split(' ')[1])
                self.cash_state.required_amount = required_amount
                self.set_collector(CollectorPosition.COLLECT)
                self.open_cash_inputs()
                self.results.put(CashControllerMessage.ACCEPTING_CASH.value)
                self.last_reported_amount = 0
                self.cash_state.status = Status.ACCEPTING_CASH

    def close_cash_inputs(self):
        self.note_register.close()
        self.coin_register.close()

    def open_cash_inputs(self):
        self.note_register.open()
        self.coin_register.open()

    # Accepting Cash, Command deny Cash
    def cancel_cash(self, command=None):
        if self.cash_state.status == Status.PAYMENT_READY:
            if self.not_registering():
                self.drop_payment()
            else:
                return False
        elif self.cash_state.status == Status.ACCEPTING_CASH:
            if self.not_registering():
                self.close_cash_inputs()
                self.reset_cash_state()
            else:
                return False
        elif self.cash_state.status == Status.DENYING_CASH:
            return True

        assert False

    # Accepting Cash, no command, but waiting for full balance or cancel request
    def update_payment_status(self, command=None):
        with self.cash_state.BALANCE_LOCK:
            if self.cash_state.balance >= self.cash_state.required_amount:
                if self.not_registering():
                    self.close_cash_inputs()
                    self.cash_state.status = Status.PAYMENT_READY
                    self.last_reported_amount = self.cash_state.balance
                    self.results.put(CashControllerMessage.PAYMENT_READY.value)
                    return True
            else:
                if not self.last_reported_amount or self.last_reported_amount < self.cash_state.balance:
                    try:
                        self.results.put(f'{Status.ACCEPTING_CASH.value} {self.cash_state.balance}', timeout=0)
                    except Full:
                        pass
            return False

    def start_all(self):
        self.start(), self.note_register.start(), self.coin_register.start()
        return self.note_register, self.coin_register


class CashRegister(Thread):
    def __init__(self, pulse_clearance, input_relay, pulse_pin, balance_per_pulse, controller: CashController):
        self.pulse_clearance = pulse_clearance
        self.input_relay = input_relay
        self.pulse_pin: Button = pulse_pin
        self.last_pulse_l: RLock = RLock()
        self.last_pulse: datetime = None
        self.balance_per_pulse: int = balance_per_pulse
        self.controller = controller

        self.is_open = False
        self.input_relay.off()

        super(CashRegister, self).__init__(target=self.handler)

    def handler(self):
        def when_held_handler():
            with self.controller.cash_state.BALANCE_LOCK:
                self.controller.cash_state.balance += self.balance_per_pulse
                self.last_pulse = datetime.now()

        self.pulse_pin.when_held = when_held_handler

    def open(self):
        self.input_relay.on()
        self.is_open = True

    def close(self):
        self.input_relay.off()
        self.is_open = False


class CoinAcceptorRegister(CashRegister):
    def __init__(self, controller: CashController):
        super().__init__(
            pulse_clearance=1.4,
            input_relay=OutputDevice(Pins.COIN_INPUT_RELAY),
            pulse_pin=Button(Pins.COIN_ACCEPTOR_PULSE_INPUT, hold_time=0.025),
            balance_per_pulse=10,
            controller=controller
        )


class NoteAcceptorRegister(CashRegister):
    def __init__(self, controller: CashController):
        super().__init__(
            pulse_clearance=1.6,
            input_relay=OutputDevice(Pins.NOTE_INPUT_RELAY),
            pulse_pin=Button(Pins.NOTE_ACCEPTOR_PULSE_INPUT, hold_time=0.045),
            balance_per_pulse=500,
            controller=controller
        )
