import tkinter as tk
from tkinter import ttk
import serial
import serial.tools.list_ports
import threading
import time

# =========================================================
# CRC16 XMODEM
# =========================================================

def crc16_xmodem(data: bytes):

    crc = 0x0000

    for byte in data:

        crc ^= (byte << 8)

        for _ in range(8):

            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc <<= 1

            crc &= 0xFFFF

    return crc


def build_packet(cmd: str):

    data = cmd.encode()

    crc = crc16_xmodem(data)

    crc_bytes = crc.to_bytes(2, "big")

    packet = data + crc_bytes + b'\r'

    return packet


# =========================================================
# SERIAL DRIVER
# =========================================================

class SerialDriver:

    def __init__(self):

        self.ser = None
        self.port = None

    def connect(self, port):

        self.port = port

        self.ser = serial.Serial(
            port=port,
            baudrate=2400,
            bytesize=8,
            parity='N',
            stopbits=1,
            timeout=1
        )

    def disconnect(self):

        if self.ser and self.ser.is_open:
            self.ser.close()

    def send(self, cmd):

        if not self.ser or not self.ser.is_open:
            return None

        packet = build_packet(cmd)

        try:

            self.ser.reset_input_buffer()

            self.ser.write(packet)

            response = self.ser.readline()

            return response

        except Exception as e:

            print("Serial error:", e)

            return None


# =========================================================
# AXPERT PROTOCOL
# =========================================================

class AxpertProtocol:

    def __init__(self, driver):

        self.driver = driver

    def qpigs(self):
        return self.driver.send("QPIGS")

    def qmod(self):
        return self.driver.send("QMOD")

    def qpiri(self):
        return self.driver.send("QPIRI")


# =========================================================
# MAIN APPLICATION
# =========================================================

class AxpertApp(tk.Tk):

    def __init__(self):

        super().__init__()

        self.title("AXPERT MONITOR PRO")
        self.geometry("1100x700")

        self.driver = SerialDriver()
        self.axpert = AxpertProtocol(self.driver)

        self.running = False

        self.create_ui()

    # =====================================================
    # UI
    # =====================================================

    def create_ui(self):

        top = ttk.Frame(self)
        top.pack(fill="x", padx=10, pady=10)

        ttk.Label(top, text="Porta COM").pack(side="left")

        self.combo_ports = ttk.Combobox(top, width=10, state="readonly")
        self.combo_ports.pack(side="left", padx=5)

        ttk.Button(top, text="Atualizar", command=self.update_ports).pack(side="left")
        ttk.Button(top, text="Conectar", command=self.connect).pack(side="left", padx=5)
        ttk.Button(top, text="Desconectar", command=self.disconnect).pack(side="left")

        self.status = ttk.Label(top, text="DESCONECTADO", foreground="red")
        self.status.pack(side="right")

        self.update_ports()

        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True)

        self.tab_status = self.create_table("Status Geral")
        self.tab_battery = self.create_table("Bateria")
        self.tab_pv = self.create_table("Solar PV")

        log_frame = ttk.LabelFrame(self, text="Log Serial")
        log_frame.pack(fill="x", padx=10, pady=10)

        self.log = tk.Text(log_frame, height=8)
        self.log.pack(fill="x")

    def create_table(self, name):

        frame = ttk.Frame(self.tabs)

        self.tabs.add(frame, text=name)

        tree = ttk.Treeview(frame, columns=("desc", "value"), show="headings")

        tree.heading("desc", text="Descrição")
        tree.heading("value", text="Valor")

        tree.column("desc", width=400)
        tree.column("value", width=200)

        tree.pack(fill="both", expand=True)

        frame.tree = tree

        return frame

    # =====================================================
    # SERIAL
    # =====================================================

    def update_ports(self):

        ports = serial.tools.list_ports.comports()

        names = [p.device for p in ports]

        self.combo_ports["values"] = names

        if names:
            self.combo_ports.current(0)

    def connect(self):

        port = self.combo_ports.get()

        try:

            self.driver.connect(port)

            self.running = True

            self.status.config(text="CONECTADO", foreground="green")

            threading.Thread(target=self.loop, daemon=True).start()

            self.log_msg(f"Conectado em {port}")

        except Exception as e:

            self.log_msg(str(e))

    def disconnect(self):

        self.running = False

        self.driver.disconnect()

        self.status.config(text="DESCONECTADO", foreground="red")

        self.log_msg("Desconectado")

    # =====================================================
    # LOOP
    # =====================================================

    def loop(self):

        while self.running:

            self.read_qpigs()

            self.read_qmod()

            time.sleep(2)

    # =====================================================
    # COMMAND READERS
    # =====================================================

    def read_qpigs(self):

        resp = self.axpert.qpigs()

        if not resp:
            return

        try:

            text = resp.decode(errors="ignore").strip()

            self.log_msg("QPIGS -> " + text)

            data = text.strip("()").split()

            if len(data) < 19:
                return

            status = [
                ("Tensão Rede", data[0] + " V"),
                ("Frequência Rede", data[1] + " Hz"),
                ("Tensão Saída", data[2] + " V"),
                ("Frequência Saída", data[3] + " Hz"),
                ("Carga", data[6] + " %"),
                ("Barramento DC", data[7] + " V"),
                ("Temperatura", data[11] + " °C")
            ]

            battery = [
                ("Tensão Bateria", data[8] + " V"),
                ("Corrente Carga", data[9] + " A"),
                ("SOC", data[10] + " %")
            ]

            pv = [
                ("Corrente PV", data[12] + " A"),
                ("Tensão PV", data[13] + " V"),
                ("Potência PV", data[18] + " W")
            ]

            self.update_table(self.tab_status.tree, status)
            self.update_table(self.tab_battery.tree, battery)
            self.update_table(self.tab_pv.tree, pv)

        except:
            pass

    def read_qmod(self):

        resp = self.axpert.qmod()

        if resp:

            text = resp.decode(errors="ignore").strip()

            self.log_msg("QMOD -> " + text)

    # =====================================================
    # UI HELPERS
    # =====================================================

    def update_table(self, tree, rows):

        tree.delete(*tree.get_children())

        for r in rows:
            tree.insert("", "end", values=r)

    def log_msg(self, msg):

        self.log.insert("end", msg + "\n")

        self.log.see("end")


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    app = AxpertApp()

    app.mainloop()
