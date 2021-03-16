from enum import Enum


class CashRegisterCommand(Enum):
    DENY_CASH = "DENY_CASH"
    ACCEPT_CASH = "ACCEPT_CASH"
    TAKE_MONEY = "TAKE_MONEY"


class CashRegisterStatus(Enum):
    ACCEPTING_CASH = "ACCEPTING_CASH"
    DENYING_CASH = "DENYING_CASH"
    PAYMENT_READY = "PAYMENT_READY"
    PAYMENT_COLLECTED = "PAYMENT_COLLECTED"
    PAYMENT_DROPPED = "PAYMENT_DROPPED"


class MessageQueueNames(Enum):
    CLIENT_CONTROLLER_RESPONSES = '/ft_client_controller_responses'
    CLIENT_CONTROLLER_REQUESTS = '/ft_client_controller_requests'
