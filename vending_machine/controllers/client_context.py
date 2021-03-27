from ..machine_configuration import MachineConfiguration
from ..machine_identity import MachineIdentity
import swagger_client


class ClientContext:
    def __init__(
            self, api: swagger_client.DefaultApi = None,
            identity: MachineIdentity = None,
            config: MachineConfiguration = None
    ):
        self.identity = identity or MachineIdentity()
        self.config = config or MachineConfiguration()

        self._api_conf = swagger_client.Configuration()
        self._api_conf.api_key = self.identity.api_key
        self._api_client = swagger_client.ApiClient(self._api_conf)

        self.api = api or swagger_client.DefaultApi(self._api_client)
