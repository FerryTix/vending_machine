import posix_ipc as ipc
from threading import Lock, Thread
from time import sleep
from gpiozero.pins.mock import MockFactory
from gpiozero import Device, Button
from pins import Pins

# Set the default pin factory to a mock factory
Device.pin_factory = MockFactory()

COMMAND_LOCK = Lock()


class CashState:
    CASH_MQ_LOCK = Lock()
    cash_mq = ipc.MessageQueue('/ft_cash_register', ipc.O_CREAT)
    BALANCE_LOCK = Lock()
    balance = 0
    required_amount = 0
    accept_cash = False


class CashController(Thread):
    cmd_mq = ipc.MessageQueue('/ft_cash_controller', ipc.O_CREAT)

    def __init__(self):
        def handler():
            while True:
                cmd, prio = self.cmd_mq.receive(timeout=0.1 if CashState.accept_cash else None)
                if cmd:
                    if cmd.startswith("ACCEPT CASH "):
                        self.accept_cash(amount=int(cmd["ACCEPT CASH ":]))
                        with CashState.CASH_MQ_LOCK:
                            CashState.cash_mq.send("ACCEPTING CASH")
                    if cmd.startswith("DENY CASH"):
                        self.cancel_cash()
                        with CashState.CASH_MQ_LOCK:
                            CashState.cash_mq.send("DENYING CASH")
                    if cmd.startswith("TAKE MONEY"):
                        self.take_money()
                        with CashState.CASH_MQ_LOCK:
                            CashState.cash_mq.send("PAYMENT COLLECTED")
                    else:
                        raise RuntimeError(f"Undefined Command {cmd}!")
                else:
                    with CashState.BALANCE_LOCK:
                        if CashState.balance >= CashState.required_amount:
                            self.deny_cash()
                    with CashState.CASH_MQ_LOCK:
                        CashState.cash_mq.send("PAYMENT READY")

        super().__init__(target=handler)

    @staticmethod
    def accept_cash(amount):
        # Setup hardware to accept Cash:
        # Open Coin Acceptor SET and close Note Acceptor Inhibit Circuit
        with CashState.BALANCE_LOCK:
            CashState.accept_cash = True
            CashState.required_amount = amount
        note_acceptor_register_thread.open()
        coin_acceptor_register_thread.open()

    @staticmethod
    def deny_cash():
        CashState.accept_cash = False
        na_lock_acquired = note_acceptor_register_thread.REGISTERING_INPUT.acquire(blocking=False)
        if na_lock_acquired:
            note_acceptor_register_thread.close()
            note_acceptor_register_thread.REGISTERING_INPUT.release()
        with coin_acceptor_register_thread.REGISTERING_INPUT:
            coin_acceptor_register_thread.close()
        if not na_lock_acquired:
            with note_acceptor_register_thread.REGISTERING_INPUT:
                note_acceptor_register_thread.close()

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


class NoteAcceptorRegister(Thread):
    REGISTERING_INPUT = Lock()

    def __init__(self):
        def handler():
            input_pin = Button(Pins.COIN_ACCEPTOR_PULSE_INPUT)
            while True:
                input_pin.wait_for_press()
                with self.REGISTERING_INPUT:
                    self.close()
                    with CashState.BALANCE_LOCK:
                        CashState.balance += 10
                    while True:
                        sleep(0.01)
                        # TODO: FIND OUT SUITABLE TIMEOUT
                        res = input_pin.wait_for_press(timeout=1.100)
                        print(res)
                        if res:
                            with CashState.BALANCE_LOCK:
                                CashState.balance += 10
                            continue
                        break
                    self.open()

        super().__init__(target=handler)

    def open(self):
        pass

    def close(self):
        pass


class CoinAcceptorRegister(Thread):
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
                        sleep(0.110)
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
        pass

    def close(self):
        pass


cash_controller_thread = CashController()
note_acceptor_register_thread = NoteAcceptorRegister()
coin_acceptor_register_thread = CoinAcceptorRegister()

cash_controller_thread.start()
note_acceptor_register_thread.start()
coin_acceptor_register_thread.start()
