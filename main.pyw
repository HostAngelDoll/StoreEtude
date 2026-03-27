import sys
import os
import ctypes
from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow
from controllers.main_controller import MainController
from core.db_manager_utils import init_databases

def main():
    if os.name == 'nt':
        myappid = 'storeetude.precuremanager.desktopcenter.1'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

    # Initialize databases if they don't exist
    init_databases()

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Instantiate UI
    window = MainWindow()

    # Instantiate Controller and connect it to UI
    controller = MainController(window)

    # Handle close event to ensure clean shutdown
    window.closed.connect(controller.shutdown)

    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
