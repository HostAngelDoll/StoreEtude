import sys
import os
import re
import subprocess
import json
import socket

from core.config_manager import ConfigManager

class WhitelistManager:
    def __init__(self):
        self.config_manager = ConfigManager()
        self.whitelist_path = os.path.join(self.config_manager.config_dir, "whitelist.json")
        self.whitelist = []
        self.load()

    def load(self):
        if os.path.exists(self.whitelist_path):
            try:
                with open(self.whitelist_path, 'r', encoding='utf-8') as f:
                    self.whitelist = json.load(f)
            except Exception as e:
                print(f"Error loading whitelist: {e}")
                self.whitelist = []

    def save(self):
        try:
            with open(self.whitelist_path, 'w', encoding='utf-8') as f:
                json.dump(self.whitelist, f, indent=4)
        except Exception as e:
            print(f"Error saving whitelist: {e}")

    def add_network(self, network_data):
        self.whitelist.append(network_data)
        self.save()

    def remove_network(self, index):
        if 0 <= index < len(self.whitelist):
            del self.whitelist[index]
            self.save()

    def get_whitelist(self):
        return self.whitelist

    def get_current_network_info(self):
        """
        Improved network detection logic for Windows environments.
        """
        networks = []

        # 1. Get WiFi info using netsh
        wifi_info = {"ssid": None, "bssid": None}
        try:
            netsh_output = subprocess.check_output("netsh wlan show interfaces", shell=True).decode(errors="ignore")
            wifi_info["ssid"] = self._extract_value(netsh_output, r"SSID")
            wifi_info["bssid"] = self._extract_value(netsh_output, r"BSSID")
        except:
            pass

        # 2. Get IP info using socket
        local_ip = ""
        try:
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
        except:
            pass

        # 3. Get Gateway info using ipconfig
        gateway = ""
        try:
            ipconfig_output = subprocess.check_output("ipconfig", shell=True).decode(errors="ignore")
            # We look for the gateway in a way that handles multiple adapters
            # but usually the one with the default gateway is the active one.
            # The regex searches for the first occurrence of 'Default Gateway' or 'Puerta de enlace predeterminada'
            gw_match = re.search(r"(?:Default Gateway|Puerta de enlace predeterminada)[ .]*: ([\d\.]+)", ipconfig_output)
            if gw_match:
                gateway = gw_match.group(1)
        except:
            pass

        # If we have WiFi info, create a WiFi entry
        if wifi_info["ssid"] or wifi_info["bssid"]:
            networks.append({
                "ip": local_ip,
                "gateway": gateway,
                "type": "WiFi",
                "ssid": wifi_info["ssid"] or "",
                "bssid": wifi_info["bssid"] or "",
                "name": wifi_info["ssid"] or "WiFi Network"
            })

        # If we have an IP but no WiFi was detected, assume Ethernet or some other active connection
        elif local_ip and local_ip != "127.0.0.1":
            networks.append({
                "ip": local_ip,
                "gateway": gateway,
                "type": "Ethernet",
                "ssid": "",
                "bssid": "",
                "name": "Ethernet Connection"
            })

        return networks

    def _extract_value(self, text, label):
        # Escaping label just in case, and making it flexible for any characters before it
        match = re.search(rf"[ ]+{re.escape(label)}[ .]*: (.+)", text)
        if match:
            return match.group(1).strip()
        return None

    def check_connection_status(self):
        if not self.whitelist:
            return "empty"

        current_networks = self.get_current_network_info()
        if not current_networks:
            return "offline"

        for curr in current_networks:
            for allowed in self.whitelist:
                # BSSID match is primary for WiFi
                if curr['type'] == "WiFi" and curr['bssid'] and allowed['bssid'] and curr['bssid'].lower() == allowed['bssid'].lower():
                    return "accepted"

                # Fallback to Gateway + SSID for WiFi or Gateway for Ethernet
                if curr['gateway'] and allowed['gateway'] and curr['gateway'] == allowed['gateway']:
                    if curr['type'] == "WiFi":
                        if curr['ssid'] and allowed['ssid'] and curr['ssid'].lower() == allowed['ssid'].lower():
                            return "accepted"
                    else:
                        return "accepted"

        return "unacceptable"

if __name__ == "__main__":
    mgr = WhitelistManager()
    print("Current network info:")
    print(json.dumps(mgr.get_current_network_info(), indent=4))
    print(f"Connection status: {mgr.check_connection_status()}")
