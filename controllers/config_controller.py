from config_manager import ConfigManager

class ConfigController:
    def __init__(self):
        self.config = ConfigManager()

    def get_settings(self):
        return self.config.settings

    def update_settings(self, key, value, save=True):
        self.config.set(key, value, save=save)

    def save_settings(self):
        self.config.save()

    def get_column_config(self, table_name, col_name):
        return self.config.get_column_config(table_name, col_name)

    def set_column_config(self, table_name, col_name, width=None, locked=None, save=True):
        self.config.set_column_config(table_name, col_name, width, locked, save)

    def move_config(self, new_path):
        return self.config.move_config_file(new_path)
