import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QTabWidget, QLabel, QPushButton, QHBoxLayout)
from PyQt6.QtCore import Qt
from db_manager import init_databases

class PrecureManagerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Configuración principal de la ventana
        self.setWindowTitle("Precure Media Manager - Core System")
        self.setGeometry(100, 100, 900, 600) # x, y, ancho, alto
        
        # Widget central y layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Sistema de Pestañas
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        
        # Inicializar las pestañas
        self.init_resources_tab()
        self.init_registry_tab()
        self.init_seasons_tab()

    def init_resources_tab(self):
        """Pestaña para gestionar T Resources (Inventario)"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        title = QLabel("Gestión de Recursos (T Resources)")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        
        # Aquí Jules podrá agregar una QTableView conectada a tu base de datos
        placeholder = QLabel("Aquí irá la tabla con el ID, Ep Num, Title y Path of File.")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        btn_scan = QPushButton("Escanear Directorio SMB/Local")
        
        layout.addWidget(title)
        layout.addWidget(placeholder)
        layout.addWidget(btn_scan)
        
        self.tabs.addTab(tab, "Recursos")

    def init_registry_tab(self):
        """Pestaña para gestionar T Registry (Historial)"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(QLabel("Historial de Visualización (T Registry)"))
        self.tabs.addTab(tab, "Registros")

    def init_seasons_tab(self):
        """Pestaña para gestionar T Seasons (Metadatos)"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(QLabel("Configuración de Temporadas (T Seasons)"))
        self.tabs.addTab(tab, "Temporadas")

if __name__ == "__main__":
    # Inicializar bases de datos
    init_databases()

    app = QApplication(sys.argv)
    
    # Aplicar un estilo básico (opcional, Jules puede mejorarlo después)
    app.setStyle("Fusion") 
    
    window = PrecureManagerApp()
    window.show()
    sys.exit(app.exec())
