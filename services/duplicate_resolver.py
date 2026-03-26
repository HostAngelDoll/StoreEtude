import time

class DuplicateResolver:
    def __init__(self):
        self._choice = None
        self._apply_all = False
        self._last_action = 0

    def resolve(self, title, request_callback):
        if self._apply_all: return self._last_action
        self._choice = None
        request_callback(title)
        while self._choice is None: time.sleep(0.01)
        action, self._apply_all = self._choice
        self._last_action = action
        return action

    def set_choice(self, choice, apply_all):
        self._choice = (choice, apply_all)
