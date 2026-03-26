from network.validator import WhitelistValidator
from config_manager import ConfigManager

class NetworkController:
    def __init__(self):
        config_dir = ConfigManager().config_dir
        self.validator = WhitelistValidator(config_dir)

    def get_whitelist(self):
        return self.validator.get_whitelist()

    def add_network(self, data):
        self.validator.add_network(data)

    def remove_network(self, index):
        self.validator.remove_network(index)

    def get_current_network(self):
        return self.validator.get_current_network_info()

    def check_status(self):
        return self.validator.check_connection_status()
