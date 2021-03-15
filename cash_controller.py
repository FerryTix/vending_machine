import posix_ipc as ipc
from threading import Lock, Thread, Semaphore
from time import sleep
from gpiozero.pins.mock import MockFactory
from gpiozero import Device, Button, OutputDevice
from pins import Pins
import os
from client_constants import CashRegisterCommand, CashRegisterStatus, MessageQueueNames

# Set the default pin factory to a mock factory
if os.environ.get('TESTING_ENVIRONMENT', None):
    Device.pin_factory = MockFactory()


class CashState:
    BALANCE_LOCK = Lock()
    balance = 0
    required_amount = 0
    accept_cash = False


class CashController(Thread):
    cash_mq = ipc.MessageQueue(MessageQueueNames.CLIENT_CONTROLLER_RESPONSES, ipc.O_CREAT)
    cmd_mq = ipc.MessageQueue(MessageQueueNames.CLIENT_CONTROLLER_REQUESTS, ipc.O_CREAT)
    _instance = None
    cash_input_sem = Semaphore(value=4)

    def __init__(self):
        if CashController._instance:
            raise RuntimeError
        else:
            CashController._instance = self

        self.note_register = NoteAcceptorRegister()
        self.coin_register = CoinAcceptorRegister()

        def handler():
            while True:
                cmd, prio = CashController.cmd_mq.receive(timeout=0.1 if CashState.accept_cash else None)
                if cmd:
                    if cmd.startswith(CashRegisterCommand.ACCEPT_CASH):
                        self.accept_cash(amount=int(cmd.split(', ')[1]))
                        CashController.cash_mq.send(CashRegisterStatus.ACCEPTING_CASH)
                    if cmd.startswith(CashRegisterCommand.DENY_CASH):
                        self.cancel_cash()
                        CashController.cash_mq.send(CashRegisterStatus.DENYING_CASH)
                    if cmd.startswith(CashRegisterCommand.TAKE_MONEY):
                        self.take_money()
                        CashController.cash_mq.send(CashRegisterStatus.PAYMENT_COLLECTED)
                    else:
                        raise RuntimeError(f"Undefined Command {cmd}!")
                else:
                    with CashState.BALANCE_LOCK:
                        if CashState.balance >= CashState.required_amount:
                            self.deny_cash()
                    CashController.cash_mq.send(CashRegisterStatus.PAYMENT_READY)

        super().__init__(target=handler)

    def accept_cash(self, amount):
        # Setup hardware to accept Cash:
        # Open Coin Acceptor SET and close Note Acceptor Inhibit Circuit
        with CashState.BALANCE_LOCK:
            CashState.accept_cash = True
            CashState.required_amount = amount
        self.note_register.open()
        self.coin_register.open()

    def deny_cash(self):
        CashState.accept_cash = False
        na_lock_acquired = self.note_register.REGISTERING_INPUT.acquire(blocking=False)
        if na_lock_acquired:
            self.note_register.close()
            self.note_register.REGISTERING_INPUT.release()
        with self.coin_register.REGISTERING_INPUT:
            self.coin_register.close()
        if not na_lock_acquired:
            with self.note_register.REGISTERING_INPUT:
                self.note_register.close()

    def cancel_cash(self):
        # Setup hardware to deny Cash:
        # 1. Close Coin Acceptor SET and open Note Acceptor Inhibit Circuit
        self.deny_cash()

        # 2. Give back money
        if CashState.balance:
            self.drop_money()

    @staticmethod
    def drop_money():
        # Set collector switch to drop all the money that has been collected into the change box
        with CashState.BALANCE_LOCK:
            CashState.balance = 0

    @staticmethod
    def issue_change(amount):
        # Give out Change
        denominations = {200: 16, 100: 17, 50: 18, 20: 19, 10: 20}

        if amount % 10:
            raise RuntimeError
        while amount:
            for d in denominations:
                if d <= amount:
                    amount -= d
                    pin = denominations[d]
                    # do something with pin
                    break

    def take_money(self):
        # 1. set switch to drop money into box

        # reset balance
        with CashState.BALANCE_LOCK:
            CashState.balance = 0

        # 2. Issue Change
        with CashState.BALANCE_LOCK:
            if CashState.required_amount < CashState.balance:
                self.issue_change(CashState.balance - CashState.required_amount)

    def start_all(self):
        return self.start(), self.note_register.start(), self.coin_register.start()


class NoteAcceptorRegister(Thread):
    REGISTERING_INPUT = Lock()

    def __init__(self):
        def handler():
            input_pin = Button(Pins.NOTE_ACCEPTOR_PULSE_INPUT)
            while True:
                input_pin.wait_for_press()
                with self.REGISTERING_INPUT:
                    self.close()
                    with CashState.BALANCE_LOCK:
                        CashState.balance += 500
                    while True:
                        sleep(0.01)
                        # TODO: FIND OUT SUITABLE TIMEOUT
                        res = input_pin.wait_for_press(timeout=0.100)
                        print(res)
                        if res:
                            with CashState.BALANCE_LOCK:
                                CashState.balance += 500
                            continue
                        break
                    self.open()

        super().__init__(target=handler)

    def open(self):
        self.input_relay.on()

    def close(self):
        self.input_relay.off()


class CoinAcceptorRegister(Thread):
    REGISTERING_INPUT = Lock()

    def __init__(self):
        def handler():
            input_pin = Button(Pins.COIN_ACCEPTOR_PULSE_INPUT)
            while True:
                input_pin.wait_for_press()
                sleep(0.01)
                if input_pin.active_time or 0 < 0.01:
                    continue
                else:
                    CashController.cash_input_sem.acquire()
                    with self.REGISTERING_INPUT:
                        self.close()
                        with CashState.BALANCE_LOCK:
                            CashState.balance += 10
                        while True:
                            res = input_pin.wait_for_press(timeout=0.110)
                            print(res)
                            if res:
                                with CashState.BALANCE_LOCK:
                                    CashState.balance += 10
                                continue
                            break
                        self.open()
                    CashController.cash_input_sem.release()

        super().__init__(target=handler)

    def open(self):
        pass

    def close(self):
        pass


if __name__ == '__main__':
    controller = CashController()
    ctrl, notes, coins = controller.start_all()
