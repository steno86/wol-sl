from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import psutil
from wakeonlan import send_magic_packet
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///devices.db'
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)

# Datenbankmodelle
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(80), nullable=False)
    can_add_devices = db.Column(db.Boolean, default=False)
    can_send_wol = db.Column(db.Boolean, default=False)

class Device(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    mac = db.Column(db.String(17), nullable=False)
    interface = db.Column(db.String(80), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def get_ip_address(interface):
    addrs = psutil.net_if_addrs().get(interface)
    for addr in addrs:
        if addr.family == psutil.AF_INET:
            return addr.address
    return None

def init_db():
    with app.app_context():
        db.create_all()

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.password == password:
            login_user(user)
            return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    devices = Device.query.all()
    interfaces = {iface: get_ip_address(iface) for iface in psutil.net_if_addrs().keys()}
    return render_template('index.html', devices=devices, interfaces=interfaces)

@app.route('/add', methods=['POST'])
@login_required
def add_device():
    if current_user.can_add_devices:
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
    if current_user.can_send_wol:
        device = Device.query.get(device_id)
        if device:
            ip_address = get_ip_address(device.interface)
            send_magic_packet(device.mac, ip_address=ip_address)
    return redirect(url_for('index'))

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)
