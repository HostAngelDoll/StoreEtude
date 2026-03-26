import sys
import os
import re
import subprocess
import json

# Add parent directory to path to import ConfigManager
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from config_manager import ConfigManager
except ImportError:
    class ConfigManager:
        def __init__(self):
            self.config_dir = "."

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
        # network_data: {name, ssid, bssid, gateway, ip, type}
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
        Returns info about current network connection.
        Returns a list of dicts (could be multiple interfaces)
        """
        networks = []

        # 1. Get IP and Gateway using ipconfig
        try:
            # We use try/except because ipconfig might not exist on all environments
            # but this app is primarily Windows-focused
            process = subprocess.run(["ipconfig"], capture_output=True, text=True, shell=True)
            ipconfig_output = process.stdout

            # Extract sections
            sections = re.split(r'\n(?=[^\s])', ipconfig_output)
            for section in sections:
                if "IPv4 Address" in section or "Dirección IPv4" in section:
                    ip_match = re.search(r'(?:IPv4 Address|Dirección IPv4)[ .:]+ ([\d.]+)', section)
                    gw_match = re.search(r'(?:Default Gateway|Puerta de enlace predeterminada)[ .:]+ ([\d.]+)', section)

                    if ip_match:
                        ip = ip_match.group(1)
                        gw = gw_match.group(1) if gw_match else ""

                        # Determine if it's WiFi or Ethernet based on section header
                        net_type = "Ethernet"
                        if any(kw in section for kw in ["Wi-Fi", "Wireless", "Inalámbrica"]):
                            net_type = "WiFi"

                        net_info = {
                            "ip": ip,
                            "gateway": gw,
                            "type": net_type,
                            "ssid": "",
                            "bssid": "",
                            "name": ""
                        }

                        # 2. If it's WiFi, get SSID and BSSID using netsh
                        if net_type == "WiFi":
                            try:
                                netsh_process = subprocess.run(["netsh", "wlan", "show", "interfaces"], capture_output=True, text=True, shell=True)
                                netsh_output = netsh_process.stdout
                                ssid_match = re.search(r' SSID[ ]+: (.+)', netsh_output)
                                bssid_match = re.search(r' BSSID[ ]+: (.+)', netsh_output)
                                if ssid_match:
                                    net_info["ssid"] = ssid_match.group(1).strip()
                                if bssid_match:
                                    net_info["bssid"] = bssid_match.group(1).strip()
                                net_info["name"] = net_info["ssid"]
                            except:
                                pass

                        if not net_info["name"]:
                            # For Ethernet, we might use the adapter name
                            name_match = re.search(r'^(.*?):', section.strip())
                            if name_match:
                                net_info["name"] = name_match.group(1).strip()

                        networks.append(net_info)
        except Exception as e:
            print(f"Error getting network info: {e}")

        return networks

    def check_connection_status(self):
        """
        Returns:
        - "offline": No internet/network connection
        - "accepted": Connected to a whitelisted network
        - "unacceptable": Connected to a network NOT in whitelist
        - "empty": Whitelist is empty
        """
        if not self.whitelist:
            return "empty"

        current_networks = self.get_current_network_info()
        if not current_networks:
            return "offline"

        for curr in current_networks:
            for allowed in self.whitelist:
                # BSSID match is primary
                if curr['bssid'] and allowed['bssid'] and curr['bssid'].lower() == allowed['bssid'].lower():
                    return "accepted"

                # If Ethernet or BSSID not available, check Gateway + SSID
                # Note: BSSID is more reliable for identifying a specific AP.
                # If not present, we use Gateway as a second-best option.
                gw_match = curr['gateway'] and allowed['gateway'] and curr['gateway'] == allowed['gateway']
                ssid_match = curr['ssid'] and allowed['ssid'] and curr['ssid'].lower() == allowed['ssid'].lower()

                if gw_match:
                    if curr['type'] == "WiFi":
                        if ssid_match:
                            return "accepted"
                    elif curr['type'] == "Ethernet":
                        # For ethernet, gateway + name/type might be enough
                        return "accepted"

        return "unacceptable"

if __name__ == "__main__":
    mgr = WhitelistManager()
    print("Current network info:")
    print(json.dumps(mgr.get_current_network_info(), indent=4))
    print(f"Connection status: {mgr.check_connection_status()}")
