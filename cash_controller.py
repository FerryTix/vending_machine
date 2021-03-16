from changebox import ChangeBox
import posix_ipc as ipc
from enum import Enum
from datetime import datetime
from threading import Lock, Thread, Semaphore
from gpiozero.pins.mock import MockFactory
from gpiozero import Device, Button, OutputDevice
from pins import Pins
import os
from client_constants import CashRegisterCommand, CashRegisterStatus, MessageQueueNames

# Set the default pin factory to a mock factory
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
    TAKE = "TAK E"
    COLLECT = "COLLECT"


class CashController(Thread):
    cash_mq = ipc.MessageQueue(MessageQueueNames.CLIENT_CONTROLLER_RESPONSES.value, ipc.O_CREAT)
    cmd_mq = ipc.MessageQueue(MessageQueueNames.CLIENT_CONTROLLER_REQUESTS.value, ipc.O_CREAT)
    _instance = None
    cash_input_sem = Semaphore(value=4)
    cash_state = CashState()

    def __init__(self):
        self.change_box = ChangeBox()
        self.last_reported_amount = None
        self.last_command = None
        if CashController._instance:
            raise RuntimeError
        else:
            CashController._instance = self

        self.note_register = NoteAcceptorRegister()
        self.coin_register = CoinAcceptorRegister()

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
                CashRegisterCommand.ACCEPT_CASH:
                    self.enable_cash if self.cash_state.status == Status.DENYING_CASH else
                    self.update_payment_status if self.cash_state.status == Status.ACCEPTING_CASH else None,
                CashRegisterCommand.DENY_CASH:
                    self.cancel_cash if self.cash_state.status == Status.ACCEPTING_CASH else
                    self.cancel_cash if self.cash_state.status == Status.PAYMENT_READY else None,
                CashRegisterCommand.TAKE_MONEY:
                    self.collect_payment if self.cash_state.status == Status.PAYMENT_READY else None,
            }

            try:
                cmd, _ = CashController.cmd_mq.receive(timeout=1 if self.last_command else None)
                cmd = cmd.decode("utf-8")
                command = (
                    CashRegisterCommand.ACCEPT_CASH if cmd.startswith(CashRegisterCommand.ACCEPT_CASH.value)
                    else CashRegisterCommand.DENY_CASH if cmd.startswith(CashRegisterCommand.DENY_CASH.value) else
                    CashRegisterCommand.TAKE_MONEY if cmd.startswith(CashRegisterCommand.TAKE_MONEY.value) else None
                )
                if command:
                    fun = functions[command]
                    if fun:
                        if fun(command=cmd):
                            self.last_command = None
                        else:
                            self.last_command = (command, cmd)

            except ipc.BusyError as e:
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
            self.cash_mq.send(CashRegisterStatus.PAYMENT_COLLECTED.value)
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

        self.cash_mq.send(CashRegisterStatus.PAYMENT_DROPPED.value)

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
                self.cash_mq.send(CashRegisterStatus.ACCEPTING_CASH.value)
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
                    self.cash_mq.send(CashRegisterStatus.PAYMENT_READY.value)
                    return True
            else:
                if not self.last_reported_amount or self.last_reported_amount < self.cash_state.balance:
                    try:
                        self.cash_mq.send(f'{Status.ACCEPTING_CASH.value} {self.cash_state.balance}', timeout=0)
                    except ipc.BusyError:
                        pass
            return False

    def start_all(self):
        self.start(), self.note_register.start(), self.coin_register.start()
        return self.note_register, self.coin_register


class CashRegister(Thread):
    def __init__(self, pulse_clearance, input_relay, pulse_pin, balance_per_pulse):
        self.pulse_clearance = pulse_clearance
        self.input_relay = input_relay
        self.pulse_pin: Button = pulse_pin
        self.last_pulse_l: Lock = Lock()
        self.last_pulse: datetime = None
        self.balance_per_pulse: int = balance_per_pulse

        self.is_open = False
        self.input_relay.off()

        super(CashRegister, self).__init__(target=self.handler)

    def handler(self):
        def when_held_handler():
            with CashController.cash_state.BALANCE_LOCK:
                CashController.cash_state.balance += self.balance_per_pulse
                self.last_pulse = datetime.now()

        self.pulse_pin.when_held = when_held_handler

    def open(self):
        self.input_relay.on()
        self.is_open = True

    def close(self):
        self.input_relay.off()
        self.is_open = False


class CoinAcceptorRegister(CashRegister):

    def __init__(self):
        super().__init__(
            pulse_clearance=1.4,
            input_relay=OutputDevice(Pins.COIN_INPUT_RELAY),
            pulse_pin=Button(Pins.COIN_ACCEPTOR_PULSE_INPUT, hold_time=0.025),
            balance_per_pulse=10,
        )


class NoteAcceptorRegister(CashRegister):

    def __init__(self):
        super().__init__(
            pulse_clearance=1.6,
            input_relay=OutputDevice(Pins.NOTE_INPUT_RELAY),
            pulse_pin=Button(Pins.NOTE_ACCEPTOR_PULSE_INPUT, hold_time=0.045),
            balance_per_pulse=500,
        )


if __name__ == '__main__':
    controller = CashController()
    notes, coins = controller.start_all()
