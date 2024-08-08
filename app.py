from flask import Flask, request, render_template, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import psutil
import socket
from wakeonlan import send_magic_packet
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///wol.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Benutzer- und Rollenmodelle definieren
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    can_add_devices = db.Column(db.Boolean, default=False)
    can_send_wol = db.Column(db.Boolean, default=False)

class Device(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    mac = db.Column(db.String(17), nullable=False)
    interface = db.Column(db.String(150), nullable=False)

# Datenbank initialisieren
def init_db():
    db.create_all()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Funktion zum Ermitteln der Netzwerkschnittstellen und IP-Adressen
def get_network_interfaces():
    interfaces = {}
    addrs = psutil.net_if_addrs()
    for interface_name, interface_addrs in addrs.items():
        for addr in interface_addrs:
            if addr.family == socket.AF_INET:
                interfaces[interface_name] = addr.address
    return interfaces

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Login failed. Check your username and/or password.')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    if not current_user.is_admin:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        is_admin = 'is_admin' in request.form
        can_add_devices = 'can_add_devices' in request.form
        can_send_wol = 'can_send_wol' in request.form
        
        hashed_password = generate_password_hash(password, method='sha256')
        new_user = User(username=username, password=hashed_password, is_admin=is_admin,
                        can_add_devices=can_add_devices, can_send_wol=can_send_wol)
        db.session.add(new_user)
        db.session.commit()
        flash('New user created successfully.')
    
    users = User.query.all()
    return render_template('admin.html', users=users)

@app.route('/')
@login_required
def index():
    devices = Device.query.all()
    interfaces = get_network_interfaces()
    
    return render_template('index.html', devices=devices, interfaces=interfaces)

@app.route('/add', methods=['POST'])
@login_required
def add_device():
    if not current_user.can_add_devices:
        flash('You do not have permission to add devices.')
        return redirect(url_for('index'))
    
    name = request.form['name']
    mac = request.form['mac']
    interface = request.form['interface']
    new_device = Device(name=name, mac=mac, interface=interface)
    db.session.add(new_device)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/wake/<int:device_id>')
@login_required
def wake_device(device_id):
    if not current_user.can_send_wol:
        flash('You do not have permission to send Wake-on-LAN packets.')
        return redirect(url_for('index'))
    
    device = Device.query.get(device_id)
    if device:
        ip_address = get_ip_address(device.interface)
        if ip_address:
            print(f"Attempting to send WoL packet to MAC: {device.mac} via IP: {ip_address}")
            send_magic_packet(device.mac, interface=ip_address)  # Verwende die IP-Adresse als Interface
    return redirect(url_for('index'))

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)
