from threading import Thread
from queue import Queue
from swagger_client import DefaultApi
from swagger_client.rest import ApiException
from abc import ABC
from .client_context import ClientContext
from swagger_client.models import *


class APIRequest(ABC):
    def __init__(self, context: ClientContext):
        self.context = context

    def __call__(self, api_instance: DefaultApi, **kwargs):
        pass


class GetFaehrCard(APIRequest):
    def __init__(self, uuid: str, context: ClientContext):
        super(GetFaehrCard, self).__init__(context)
        self.uuid = uuid

    def __call__(self, api_instance: DefaultApi, **kwargs):
        resp = api_instance.faehr_card_uuid_get(uuid=self.uuid)
        return resp


class GetFaehrcardBalance(APIRequest):
    def __init__(self, faehrcard: FaehrCard, context: ClientContext):
        super().__init__(context)
        self.faehrcard = faehrcard

    def __call__(self, api_instance: DefaultApi, **kwargs):
        resp = api_instance.faehr_card_uuid_balance_get(uuid=self.faehrcard.uuid)
        return resp


class PostTicketSale(APIRequest):
    def __init__(self, ticket_sale: TicketSale, context: ClientContext):
        super(PostTicketSale, self).__init__(context)
        self.signed_data = self.context.identity.signed_data(ticket_sale.to_dict())

    def __call__(self, api_instance: DefaultApi, **kwargs):
        resp = api_instance.ticket_sales_post(body=self.signed_data)
        return resp


class PostTopUp(APIRequest):
    def __init__(self, faehrcard: FaehrCard, top_up: TopUp, context: ClientContext):
        super(PostTopUp, self).__init__(context)
        self.signed_data = self.context.identity.signed_data(top_up.to_dict())
        self.faehrcard = faehrcard

    def __call__(self, api_instance: DefaultApi, **kwargs):
        resp = api_instance.faehr_card_uuid_topup_post(body=self.signed_data, uuid=self.faehrcard.uuid)
        return resp


class PatchStatus(APIRequest):
    def __init__(self, status: MachineStatus, context: ClientContext):
        super(PatchStatus, self).__init__(context)
        self.signed_data = self.context.identity.signed_data(status.to_dict())

    def __call__(self, api_instance: DefaultApi, **kwargs):
        resp = api_instance.machines_uuid_status_patch(body=self.signed_data, uuid=self.context.identity.uuid)
        return resp


class GetMachineConfig(APIRequest):
    def __init__(self, machine_config: MachineConfiguration, context: ClientContext):
        super(GetMachineConfig, self).__init__(context)
        self.machine_config = machine_config.to_dict()

    def __call__(self, api_instance: DefaultApi, **kwargs):
        resp = api_instance.machines_uuid_commands_get(uuid=self.context.identity.uuid)
        return resp


class RetrieveCommand(APIRequest):
    def __init__(self, context: ClientContext):
        super(RetrieveCommand, self).__init__(context)

    def __call__(self, api_instance: DefaultApi, **kwargs):
        resp = api_instance.machines_uuid_commands_get(self.context.identity.uuid)
        return resp


class APIController:
    def __init__(self, report_to: Queue, context: ClientContext):
        self.results = report_to
        self.api = context.api
        self.tasks = Queue()
        self.context = context

        self.request_thread = RequestThread(self)
        self.command_receiver = CommandReceiver(self)

    def start_all(self):
        self.request_thread.start()
        self.command_receiver.start()

    def request(self, request: APIRequest):
        self.tasks.put(request)


class RequestThread(Thread):
    def __init__(self, controller: APIController):
        self.controller = controller

        super(RequestThread, self).__init__(target=self.handler)

    def handler(self):
        while True:
            task = self.controller.tasks.get()
            try:
                self.controller.results.put(task(api_instance=self.controller.api))
            except ApiException as e:
                self.controller.tasks.put(task)


class CommandReceiver(Thread):
    def __init__(self, controller: APIController):
        self.controller = controller

        super(CommandReceiver, self).__init__(target=self.handler)

    def handler(self):
        while True:
            request = RetrieveCommand(context=self.controller.context)
            try:
                res = request(api_instance=self.controller.api)
                self.controller.results.put(res)
            except ApiException as e:
                if e.status == 408:
                    pass
                else:
                    raise e
