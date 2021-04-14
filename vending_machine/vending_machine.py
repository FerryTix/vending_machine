import os

os.environ.setdefault("BASE_PATH", "../frontend/")

from loguru import logger
from controllers.client_controller import ClientController
from controllers.client_context import ClientContext

if __name__ == '__main__':
    logger.add(open('../vending_machine.log', 'w'))
    logger.info("Starting Vending Machine")
    client_context = ClientContext()
    ctrl = ClientController(context=client_context)
    ctrl.start()
