import os
from enum import Enum
import yaml


class MachineConfiguration:
    MACHINE_CONFIG_FILE = '../machine.config.yaml'

    class KEYS(Enum):
        HOST = 'host'

    def __init__(self):
        if not (os.path.exists(MachineConfiguration.MACHINE_CONFIG_FILE) and
                os.path.isfile(MachineConfiguration.MACHINE_CONFIG_FILE)):
            self.host = '/'
            self.update_config_file()
        else:
            with open(MachineConfiguration.MACHINE_CONFIG_FILE) as conf:
                root = yaml.safe_load(conf.read())

            self.host = root[self.KEYS.HOST]

    def update_config_file(self):
        with open(MachineConfiguration.MACHINE_CONFIG_FILE, 'w') as conf:
            conf.write(yaml.safe_dump(
                {
                    self.KEYS.HOST: self.host,
                }
            ))
