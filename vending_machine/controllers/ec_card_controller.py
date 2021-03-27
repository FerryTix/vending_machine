from threading import Thread


class ECCardController(Thread):
    def __init__(self, *args, **kwargs):
        super(ECCardController, self).__init__(target=self.handler)

    def handler(self):
        pass

    def start_all(self):
        pass
