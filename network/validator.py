import os
import json
import sys
from network.detector_windows import WindowsNetworkDetector
from network.detector_linux import LinuxNetworkDetector

class WhitelistValidator:
    def __init__(self, config_dir):
        self.whitelist_path = os.path.join(config_dir, "whitelist.json")
        self.whitelist = []
        self.detector = WindowsNetworkDetector() if sys.platform == "win32" else LinuxNetworkDetector()
        self.load()

    def load(self):
        if os.path.exists(self.whitelist_path):
            try:
                with open(self.whitelist_path, 'r', encoding='utf-8') as f:
                    self.whitelist = json.load(f)
            except: self.whitelist = []

    def save(self):
        try:
            with open(self.whitelist_path, 'w', encoding='utf-8') as f:
                json.dump(self.whitelist, f, indent=4)
        except: pass

    def get_whitelist(self): return self.whitelist

    def add_network(self, data):
        self.whitelist.append(data)
        self.save()

    def remove_network(self, index):
        if 0 <= index < len(self.whitelist):
            del self.whitelist[index]
            self.save()

    def get_current_network_info(self):
        return self.detector.get_current_network_info()

    def check_connection_status(self):
        if not self.whitelist: return "empty"
        current_networks = self.detector.get_current_network_info()
        if not current_networks: return "offline"

        for curr in current_networks:
            for allowed in self.whitelist:
                if curr['type'] == "WiFi" and curr['bssid'] and allowed['bssid'] and curr['bssid'].lower() == allowed['bssid'].lower():
                    return "accepted"
                if curr['gateway'] and allowed['gateway'] and curr['gateway'] == allowed['gateway']:
                    if curr['type'] == "WiFi":
                        if curr['ssid'] and allowed['ssid'] and curr['ssid'].lower() == allowed['ssid'].lower():
                            return "accepted"
                    else: return "accepted"
        return "unacceptable"
