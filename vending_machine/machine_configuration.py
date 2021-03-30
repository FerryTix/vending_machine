import os
from enum import Enum
import yaml


class MachineConfiguration:
    file_location = './machine.config.yaml'

    class KEYS(Enum):
        HOST = 'host'

    def __init__(self):
        if not (os.path.exists(MachineConfiguration.file_location) and
                os.path.isfile(MachineConfiguration.file_location)):
            self.update_config_file()
        else:
            with open(MachineConfiguration.file_location) as conf:
                root = yaml.safe_load(conf.read())

            self.host = root[self.KEYS.HOST]

    def update_config_file(self):
        with open(MachineConfiguration.file_location, 'w') as conf:
            conf.write(yaml.safe_dump(
                {
                    self.KEYS.HOST: self.host,
                }
            ))
