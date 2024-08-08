from flask import Flask, request, render_template, redirect, url_for
import sqlite3
import psutil
import socket
from wakeonlan import send_magic_packet

app = Flask(__name__)

# SQLite Datenbank Initialisierung
def init_db():
    conn = sqlite3.connect('wol.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS devices (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        mac TEXT NOT NULL,
                        interface TEXT NOT NULL)''')
    conn.commit()
    conn.close()

# Funktion zum Ermitteln der Netzwerkschnittstellen und IP-Adressen
def get_network_interfaces():
    interfaces = {}
    addrs = psutil.net_if_addrs()
    for interface_name, interface_addrs in addrs.items():
        for addr in interface_addrs:
            if addr.family == socket.AF_INET:
                interfaces[interface_name] = addr.address
    return interfaces

# Funktion zum Ermitteln der IP-Adresse eines Interfaces
def get_ip_address(interface_name):
    try:
        addrs = psutil.net_if_addrs()
        if interface_name in addrs:
            for addr in addrs[interface_name]:
                if addr.family == socket.AF_INET:
                    return addr.address
    except KeyError:
        return None
    return None

@app.route('/')
def index():
    conn = sqlite3.connect('wol.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM devices")
    devices = cursor.fetchall()
    conn.close()
    
    # Erhalte die verfügbaren Netzwerkschnittstellen und IP-Adressen
    interfaces = get_network_interfaces()
    
    return render_template('index.html', devices=devices, interfaces=interfaces)

@app.route('/add', methods=['POST'])
def add_device():
    name = request.form['name']
    mac = request.form['mac']
    interface = request.form['interface']
    conn = sqlite3.connect('wol.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO devices (name, mac, interface) VALUES (?, ?, ?)", (name, mac, interface))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/wake/<int:device_id>')
def wake_device(device_id):
    conn = sqlite3.connect('wol.db')
    cursor = conn.cursor()
    cursor.execute("SELECT mac, interface FROM devices WHERE id=?", (device_id,))
    device = cursor.fetchone()
    conn.close()
    if device:
        mac, interface = device
        ip_address = get_ip_address(interface)
        if ip_address:
            print(f"Attempting to send WoL packet to MAC: {mac} via IP: {ip_address}")
            send_magic_packet(mac, interface=ip_address)  # Verwende die IP-Adresse als Interface
    return redirect(url_for('index'))

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)
