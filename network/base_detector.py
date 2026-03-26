from abc import ABC, abstractmethod

class NetworkDetector(ABC):
    @abstractmethod
    def get_current_network_info(self):
        pass

    def _extract_value(self, text, label):
        import re
        match = re.search(rf"[ ]+{re.escape(label)}[ .]*: (.+)", text)
        return match.group(1).strip() if match else None
