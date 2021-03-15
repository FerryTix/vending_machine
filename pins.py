from enum import IntEnum


class Pins(IntEnum):
    RELAY_1 = 18
    RELAY_2 = 26
    RELAY_3 = 19
    RELAY_4 = 13
    RELAY_5 = 6
    RELAY_6 = 5
    RELAY_7 = 21
    RELAY_8 = 20

    MAIN_POWER_RELAY = RELAY_8
    STATUS_LIGHT_RELAY = RELAY_7
    NOTE_INPUT_RELAY = RELAY_1
    COIN_INPUT_RELAY = RELAY_2

    NOTE_ACCEPTOR_PULSE_INPUT = 23
    COIN_ACCEPTOR_PULSE_INPUT = 24

    # Reserved for NFC Reader
    NFC_RST = 25
    NFC_MOSI = 10
    NFC_MISO = 9
    NFC_SCK = 11
    NFC_SDA = 8
