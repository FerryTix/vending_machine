from threading import Thread


class FrontendController(Thread):
    def __init__(self, *args, **kwargs):
        super(FrontendController, self).__init__(target=self.handler)

    def handler(self):
        pass

    def start_all(self):
        pass
