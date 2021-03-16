from enum import Enum


class CashControllerCommand(Enum):
    DENY_CASH = "DENY_CASH"
    ACCEPT_CASH = "ACCEPT_CASH"
    TAKE_MONEY = "TAKE_MONEY"


class CashControllerMessage(Enum):
    ACCEPTING_CASH = "ACCEPTING_CASH"
    DENYING_CASH = "DENYING_CASH"
    PAYMENT_READY = "PAYMENT_READY"
    PAYMENT_COLLECTED = "PAYMENT_COLLECTED"
    PAYMENT_DROPPED = "PAYMENT_DROPPED"


class NFCControllerCommand(Enum):
    START_READING = "START_READING"
    STOP_READING = "STOP_READING"


class NFCControllerMessage(Enum):
    TAG_DETECTED = "TAG_DETECTED"
    TAG_UNREADABLE = "TAG_UNREADABLE"


class FrontendMessage(Enum):
    pass


class FrontendCommand(Enum):
    pass


class MessageQueueNames(Enum):
    CASH_CONTROLLER_MESSAGES = '/ft_cash_controller_messages'
    CASH_CONTROLLER_COMMANDS = '/ft_cash_controller_commands'
    NFC_CONTROLLER_MESSAGES = '/ft_nfc_controller_messages'
    NFC_CONTROLLER_COMMANDS = '/ft_nfc_controller_commands'
    FRONTEND_MESSAGES = '/ft_frontend_messages'
    FRONTEND_COMMANDS = '/ft_frontend_commands'
