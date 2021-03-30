from .controllers.client_controller import ClientController
from .controllers.client_context import ClientContext

if __name__ == '__main__':
    client_context = ClientContext()
    ctrl = ClientController(context=client_context)
    ctrl.start()
