from enum import Enum


class CashRegisterCommand(Enum):
    DENY_CASH = "DENY CASH"
    ACCEPT_CASH = "ACCEPT CASH"
    TAKE_MONEY = "TAKE_MONEY"


class CashRegisterStatus(Enum):
    ACCEPTING_CASH = "ACCEPTING CASH"
    DENYING_CASH = "DENYING CASH"
    PAYMENT_READY = "PAYMENT READY"
    PAYMENT_COLLECTED = "PAYMENT COLLECTED"

class MessageQueueNames(Enum):
    CLIENT_CONTROLLER_RESPONSES = '/ft_client_controller_responses'
    CLIENT_CONTROLLER_REQUESTS = '/ft_client_controller_requests'
