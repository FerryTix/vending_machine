from enum import IntEnum
from threading import Thread, RLock
from gpiozero.pins.mock import MockFactory
from gpiozero import Device
import os
from queue import Empty, Queue, Full
from mfrc522 import SimpleMFRC522
from uuid import UUID
from time import sleep

# Set the default pin factory to a mock factory, if in testing environment
if os.environ.get('TESTING_ENVIRONMENT', None):
    Device.pin_factory = MockFactory()


class NFCController(Thread):
    class Tasks(IntEnum):
        READ_TAG = 0b01
        STOP_READING = 0b10

    def __init__(self, report_to: Queue, *args, **kwargs):
        self.tag_lock = RLock()
        self.last_read_tag = None
        self.results = report_to
        self.tasks = Queue()
        self.last_task = None
        self.reader = NFCReader(controller=self)
        self.read_tags = False

        super().__init__(target=self.handler)

    def handler(self):
        while True:
            if self.tasks.not_empty:
                self.last_task = self.tasks.get()
            if self.last_task:
                if self.last_task == NFCController.Tasks.READ_TAG:
                    self.read_tags = True
                    if self.last_read_tag:
                        self.results.put(self.last_read_tag)
                elif self.last_task == NFCController.Tasks.STOP_READING:
                    self.read_tags = False
                    self.last_read_tag = None

    def start_all(self):
        self.reader.start()
        self.start()


class NFCTag:
    def __init__(self, _id, data):
        self.id = _id
        self.data = data

    def is_valid(self):
        try:
            uuid = UUID(self.data)
            assert uuid.version == 4
        except AssertionError or ValueError as e:
            return False
        else:
            return True

    def get_uuid(self):
        if self.is_valid():
            return UUID(self.data)
        else:
            return None


class NFCReader(Thread):
    def __init__(self, controller: NFCController):
        self.rfc_reader = SimpleMFRC522()
        self.parent = controller
        super().__init__(target=self.handler)

    def handler(self):
        while True:
            _id, data = self.rfc_reader.read()
            with self.parent.tag_lock:
                if self.parent.read_tags:
                    self.parent.last_read_tag = NFCTag(_id, data)
            sleep(1)
