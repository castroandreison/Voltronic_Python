import tkinter as tk
from tkinter import ttk
import serial
import serial.tools.list_ports
import threading
import time

# =====================================================
# SERIAL DRIVER
# =====================================================
class SerialDriver:
    def __init__(self):
        self.ser = None
        self.port = None

    def autodetect(self):
        ports = list(serial.tools.list_ports.comports())
        for p in ports:
            if "USB" in p.description or "COM" in p.device:
                return p.device
        return None

    def connect(self):
        self.port = self.autodetect()
        if not self.port:
            raise Exception("Nenhuma porta serial encontrada")

        self.ser = serial.Serial(
            port=self.port,
            baudrate=2400,
            bytesize=8,
            parity='N',
            stopbits=1,
            timeout=1
        )

    def send(self, cmd):
        try:
            self.ser.write(cmd.encode())
            return self.ser.readline().decode(errors="ignore").strip()
        except:
            return None


# =====================================================
# AXPERT PROTOCOL
# =====================================================
class Axpert:
    def __init__(self, drv):
        self.drv = drv

    def qpigs(self): return self.drv.send("QPIGS\r")
    def qmod(self):  return self.drv.send("QMOD\r")


# =====================================================
# UI
# =====================================================
class AxpertApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("AXPERT MONITOR PRO")
        self.geometry("1280x760")
        self.configure(bg="#1e1e1e")
        self.resizable(False, False)

        self.style = ttk.Style(self)
        self.style.theme_use("default")
        self._dark_theme()

        self.driver = SerialDriver()
        self.axpert = Axpert(self.driver)

        self._build_ui()

    def _dark_theme(self):
        self.style.configure(".", background="#1e1e1e", foreground="white")
        self.style.configure("Treeview",
            background="#252526",
            fieldbackground="#252526",
            foreground="white",
            rowheight=26)
        self.style.map("Treeview", background=[("selected", "#007acc")])

    def _build_ui(self):
        self._header()
        self._notebook()
        self._log()

    def _header(self):
        frame = ttk.Frame(self, padding=10)
        frame.pack(fill="x")

        ttk.Label(frame,
            text="AXPERT INVERTER MONITOR",
            font=("Segoe UI", 18, "bold")
        ).pack(side="left")

        self.lbl_status = ttk.Label(frame,
            text="● DESCONECTADO",
            foreground="red"
        )
        self.lbl_status.pack(side="right")

    def _notebook(self):
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=10, pady=5)

        self.tabs = {}
        for name in ["Status Geral", "Bateria", "Solar / PV", "Sistema"]:
            self.tabs[name] = self._create_tab(name)

    def _create_tab(self, title):
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text=title)

        tree = ttk.Treeview(tab, columns=("desc", "value"), show="headings")
        tree.heading("desc", text="Descrição")
        tree.heading("value", text="Valor")
        tree.column("desc", width=520)
        tree.column("value", width=240, anchor="center")
        tree.pack(fill="both", expand=True, padx=10, pady=10)

        tab.tree = tree
        return tab

    def _log(self):
        frame = ttk.LabelFrame(self, text="Log RS232")
        frame.pack(fill="x", padx=10, pady=5)

        self.log = tk.Text(frame, height=6, bg="#111", fg="#00ff99")
        self.log.pack(fill="x")

    def log_msg(self, msg):
        self.log.insert("end", msg + "\n")
        self.log.see("end")

    # =====================================================
    # START / LOOP
    # =====================================================
    def start(self):
        while True:
            try:
                self.driver.connect()
                self.lbl_status.config(
                    text=f"● CONECTADO ({self.driver.port})",
                    foreground="#00ff99"
                )
                threading.Thread(target=self.loop, daemon=True).start()
                return
            except:
                self.lbl_status.config(text="● AGUARDANDO PORTA", foreground="orange")
                time.sleep(2)

    def loop(self):
        while True:
            self.read_qpigs()
            self.read_qmod()
            time.sleep(1)

    # =====================================================
    # QPIGS COMPLETO
    # =====================================================
    def read_qpigs(self):
        resp = self.axpert.qpigs()
        if not resp:
            return

        self.log_msg(f"QPIGS → {resp}")
        d = resp.strip("()").split()

        status = [
            ("Tensão Rede", f"{d[0]} V"),
            ("Frequência Rede", f"{d[1]} Hz"),
            ("Tensão Saída", f"{d[2]} V"),
            ("Frequência Saída", f"{d[3]} Hz"),
            ("Potência Aparente", f"{d[4]} VA"),
            ("Potência Ativa", f"{d[5]} W"),
            ("Carga", f"{d[6]} %"),
            ("Barramento DC", f"{d[7]} V"),
            ("Temperatura Dissipador", f"{d[11]} °C"),
        ]

        battery = [
            ("Tensão Bateria", f"{d[8]} V"),
            ("Corrente Carga", f"{d[9]} A"),
            ("SOC", f"{d[10]} %"),
            ("Corrente Descarga", f"{d[16]} A"),
            ("Tensão SCC", f"{d[15]} V"),
        ]

        pv = [
            ("Corrente PV", f"{d[12]} A"),
            ("Tensão PV", f"{d[13]} V"),
            ("Potência PV", f"{d[18]} W"),
        ]

        system = [
            ("EEPROM Version", d[17]),
            ("Status Flags", d[14]),
        ]

        self._update("Status Geral", status)
        self._update("Bateria", battery)
        self._update("Solar / PV", pv)
        self._update("Sistema", system)

    def read_qmod(self):
        resp = self.axpert.qmod()
        if resp:
            self.log_msg(f"QMOD → {resp}")

    def _update(self, tab, rows):
        tree = self.tabs[tab].tree
        tree.delete(*tree.get_children())
        for r in rows:
            tree.insert("", "end", values=r)


# =====================================================
# RUN
# =====================================================
if __name__ == "__main__":
    app = AxpertApp()
    app.after(500, app.start)
    app.mainloop()
