from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import psutil
from wakeonlan import send_magic_packet
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///instance/devices.db'
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Datenbankmodelle
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(80), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
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
    # Verzeichnis für die Datenbankdatei sicherstellen
    if not os.path.exists('instance'):
        os.makedirs('instance')

    with app.app_context():
        db.create_all()
        # Erstelle einen Admin-Benutzer, wenn keiner existiert
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', password='adminpass', is_admin=True, can_add_devices=True, can_send_wol=True)
            db.session.add(admin)
            db.session.commit()

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.password == password:
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Login fehlgeschlagen. Bitte überprüfen Sie Ihre Anmeldedaten.')
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

@app.route('/admin')
@login_required
def admin():
    if not current_user.is_admin:
        return redirect(url_for('index'))
    users = User.query.all()
    return render_template('admin.html', users=users)

@app.route('/admin/add_user', methods=['POST'])
@login_required
def add_user():
    if not current_user.is_admin:
        return redirect(url_for('index'))
    username = request.form['username']
    password = request.form['password']
    can_add_devices = 'can_add_devices' in request.form
    can_send_wol = 'can_send_wol' in request.form
    new_user = User(username=username, password=password, can_add_devices=can_add_devices, can_send_wol=can_send_wol)
    db.session.add(new_user)
    db.session.commit()
    return redirect(url_for('admin'))

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)
