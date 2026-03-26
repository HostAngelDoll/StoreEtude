import subprocess
import re
import socket
from .base_detector import NetworkDetector

class WindowsNetworkDetector(NetworkDetector):
    def get_current_network_info(self):
        networks = []
        wifi_info = {"ssid": None, "bssid": None}
        try:
            output = subprocess.check_output("netsh wlan show interfaces", shell=True).decode(errors="ignore")
            wifi_info["ssid"] = self._extract_value(output, "SSID")
            wifi_info["bssid"] = self._extract_value(output, "BSSID")
        except: pass

        local_ip = ""
        try: local_ip = socket.gethostbyname(socket.gethostname())
        except: pass

        gateway = ""
        try:
            output = subprocess.check_output("ipconfig", shell=True).decode(errors="ignore")
            match = re.search(r"(?:Default Gateway|Puerta de enlace predeterminada)[ .]*: ([\d\.]+)", output)
            if match: gateway = match.group(1)
        except: pass

        if wifi_info["ssid"] or wifi_info["bssid"]:
            networks.append({
                "ip": local_ip, "gateway": gateway, "type": "WiFi",
                "ssid": wifi_info["ssid"] or "", "bssid": wifi_info["bssid"] or "",
                "name": wifi_info["ssid"] or "WiFi Network"
            })
        elif local_ip and local_ip != "127.0.0.1":
            networks.append({
                "ip": local_ip, "gateway": gateway, "type": "Ethernet",
                "ssid": "", "bssid": "", "name": "Ethernet Connection"
            })
        return networks
