from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableView,
                             QPushButton, QMessageBox, QHeaderView, QApplication, QWidget)
from PyQt6.QtGui import QIcon, QStandardItemModel, QStandardItem
from PyQt6.QtCore import Qt
import os
from core.whitelist_manager import WhitelistManager

class WhitelistDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.mgr = WhitelistManager()
        self.setWindowIcon(QIcon(os.path.join("img", "icon.ico")))
        self.setWindowTitle("Administrar Lista Blanca de Redes")
        self.resize(800, 450)
        self.layout = QVBoxLayout(self)

        self.label_info = QLabel("Las redes aceptadas permitirán futuras funciones de exposición de materiales a LAN.")
        self.layout.addWidget(self.label_info)

        self.model = QStandardItemModel(0, 5)
        self.model.setHorizontalHeaderLabels(["Nombre", "SSID", "BSSID", "Gateway", "IP", "Eliminar"])

        self.view = QTableView()
        self.view.setModel(self.model)
        self.view.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.view.horizontalHeader().setStretchLastSection(False)
        self.layout.addWidget(self.view)

        self.refresh_table()

        btn_add_layout = QHBoxLayout()
        self.btn_add_wifi = QPushButton("Añadir red WiFi actual")
        self.btn_add_wifi.clicked.connect(lambda: self.add_current_net("WiFi"))

        self.btn_add_eth = QPushButton("Añadir red Ethernet actual")
        self.btn_add_eth.clicked.connect(lambda: self.add_current_net("Ethernet"))

        btn_add_layout.addWidget(self.btn_add_wifi)
        btn_add_layout.addWidget(self.btn_add_eth)
        self.layout.addLayout(btn_add_layout)

        # OK Button
        self.btn_close = QPushButton("Cerrar")
        self.btn_close.clicked.connect(self.accept)
        self.layout.addWidget(self.btn_close, 0, Qt.AlignmentFlag.AlignRight)

    def refresh_table(self):
        self.model.setRowCount(0)
        whitelist = self.mgr.get_whitelist()
        for i, net in enumerate(whitelist):
            row = [
                QStandardItem(net.get('name', '')),
                QStandardItem(net.get('ssid', '')),
                QStandardItem(net.get('bssid', '')),
                QStandardItem(net.get('gateway', '')),
                QStandardItem(net.get('ip', '')),
                QStandardItem("") # Placeholder for button
            ]
            self.model.appendRow(row)

            # Create a closure to capture the index
            def make_delete_func(idx):
                return lambda: self.delete_network(idx)

            btn_del = QPushButton("Eliminar")
            btn_del.clicked.connect(make_delete_func(i))
            self.view.setIndexWidget(self.model.index(i, 5), btn_del)

    def add_current_net(self, net_type):
        current_nets = self.mgr.get_current_network_info()
        found = [n for n in current_nets if n['type'] == net_type]

        if not found:
            QMessageBox.warning(self, "Error", f"No se encontró ninguna red {net_type} activa.")
            return

        # If multiple, take the first one or prompt? Let's take the first for simplicity
        net = found[0]

        # Check if already exists (by BSSID or Gateway+SSID)
        exists = False
        for existing in self.mgr.get_whitelist():
            if net['bssid'] and existing['bssid'] and net['bssid'].lower() == existing['bssid'].lower():
                exists = True; break
            if not net['bssid'] and net['gateway'] == existing['gateway'] and net['ssid'] == existing['ssid']:
                exists = True; break

        if exists:
            QMessageBox.information(self, "Información", "Esta red ya está en la lista blanca.")
            return

        self.mgr.add_network(net)
        self.refresh_table()
        QMessageBox.information(self, "Éxito", f"Red {net_type} añadida a la lista blanca.")

    def delete_network(self, index):
        net_name = self.mgr.get_whitelist()[index].get('name', 'esta red')
        res = QMessageBox.question(self, "Confirmar eliminación",
                                   f"¿Estás seguro de que deseas eliminar '{net_name}' de la lista blanca?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if res == QMessageBox.StandardButton.Yes:
            self.mgr.remove_network(index)
            self.refresh_table()
