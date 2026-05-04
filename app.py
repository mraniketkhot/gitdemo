from datetime import date, datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'change-this-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///pg_management.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    mobile = db.Column(db.String(20), unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # admin, manager, customer
    approved = db.Column(db.Boolean, default=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class PG(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    country = db.Column(db.String(100), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(255), nullable=False)
    food_charge = db.Column(db.Float, default=0)
    upi_id = db.Column(db.String(100), nullable=True)
    bank_account = db.Column(db.String(100), nullable=True)
    ifsc = db.Column(db.String(20), nullable=True)
    qr_code_url = db.Column(db.String(255), nullable=True)
    manager_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)


class Flat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    floor_number = db.Column(db.Integer, nullable=False)
    pg_id = db.Column(db.Integer, db.ForeignKey('pg.id'), nullable=False)


class Room(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    sharing_type = db.Column(db.String(20), nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    rent_per_bed = db.Column(db.Float, nullable=False)
    flat_id = db.Column(db.Integer, db.ForeignKey('flat.id'), nullable=False)


class CustomerProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    manager_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    pg_id = db.Column(db.Integer, db.ForeignKey('pg.id'), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'), nullable=True)
    full_name = db.Column(db.String(120), nullable=False)
    permanent_address = db.Column(db.String(255), nullable=False)
    emergency_contact = db.Column(db.String(120), nullable=False)
    company = db.Column(db.String(120), nullable=True)
    with_food = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), default='pending')
    deposit_amount = db.Column(db.Float, default=0)
    join_date = db.Column(db.Date, default=date.today)
    exit_date = db.Column(db.Date, nullable=True)


class RentInvoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer_profile.id'), nullable=False)
    month_label = db.Column(db.String(20), nullable=False)
    rent_amount = db.Column(db.Float, nullable=False)
    food_amount = db.Column(db.Float, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    paid = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def role_required(*roles):
    def deco(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role not in roles:
                flash('Unauthorized access', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return wrapper
    return deco


def manager_mfa_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if current_user.role == 'manager' and not session.get('manager_mfa_ok'):
            flash('MFA required. Demo OTP is 123456.', 'warning')
            return redirect(url_for('manager_mfa', next=request.path))
        return f(*args, **kwargs)
    return wrapper


@app.route('/')
def home():
    return render_template('home.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        role = request.form['role']
        username = request.form['username'].strip()
        email = request.form['email'].strip().lower()
        mobile = request.form.get('mobile', '').strip() or None

        if User.query.filter((User.username == username) | (User.email == email) | (User.mobile == mobile)).first():
            flash('Username/email/mobile already exists.', 'danger')
            return redirect(url_for('register'))

        user = User(username=username, email=email, mobile=mobile, role=role, approved=False)
        user.set_password(request.form['password'])
        db.session.add(user)
        db.session.commit()
        flash('Registered successfully. Wait for approval.', 'info')
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identifier = request.form['identifier'].strip()
        user = User.query.filter((User.username == identifier) | (User.email == identifier) | (User.mobile == identifier)).first()
        if user and user.check_password(request.form['password']):
            if not user.approved:
                flash('Your account is pending approval.', 'warning')
                return redirect(url_for('login'))
            login_user(user)
            session.pop('manager_mfa_ok', None)
            return redirect(url_for('dashboard'))
        flash('Invalid credentials.', 'danger')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for('home'))


@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'admin':
        pending = User.query.filter_by(approved=False).all()
        return render_template('admin_dashboard.html', pending=pending)

    if current_user.role == 'manager':
        pgs = PG.query.filter_by(manager_id=current_user.id).all()
        flats = Flat.query.join(PG, PG.id == Flat.pg_id).filter(PG.manager_id == current_user.id).all()
        rooms = Room.query.join(Flat, Flat.id == Room.flat_id).join(PG, PG.id == Flat.pg_id).filter(PG.manager_id == current_user.id).all()
        customers = CustomerProfile.query.filter_by(manager_id=current_user.id).all()
        unpaid = db.session.query(RentInvoice).join(CustomerProfile, RentInvoice.customer_id == CustomerProfile.id).filter(CustomerProfile.manager_id == current_user.id, RentInvoice.paid.is_(False)).all()
        return render_template('manager_dashboard.html', pgs=pgs, flats=flats, rooms=rooms, customers=customers, unpaid=unpaid)

    profile = CustomerProfile.query.filter_by(user_id=current_user.id).first()
    invoices = RentInvoice.query.filter_by(customer_id=profile.id).all() if profile else []
    return render_template('customer_dashboard.html', profile=profile, invoices=invoices)


@app.route('/admin/approve/<int:user_id>')
@login_required
@role_required('admin')
def approve_user(user_id):
    user = User.query.get_or_404(user_id)
    user.approved = True
    db.session.commit()
    flash(f'Approved {user.username}.', 'success')
    return redirect(url_for('dashboard'))


@app.route('/manager/mfa', methods=['GET', 'POST'])
@login_required
@role_required('manager')
def manager_mfa():
    if request.method == 'POST':
        if request.form.get('code') == '123456':
            session['manager_mfa_ok'] = True
            flash('MFA verified.', 'success')
            return redirect(request.args.get('next') or url_for('dashboard'))
        flash('Wrong MFA code.', 'danger')
    return render_template('manager_mfa.html')


@app.route('/manager/pg/create', methods=['GET', 'POST'])
@login_required
@role_required('manager')
def create_pg():
    if request.method == 'POST':
        pg = PG(
            name=request.form['name'],
            country=request.form['country'],
            city=request.form['city'],
            address=request.form['address'],
            food_charge=float(request.form.get('food_charge') or 0),
            manager_id=current_user.id,
        )
        db.session.add(pg)
        db.session.commit()
        flash('PG created.', 'success')
        return redirect(url_for('dashboard'))
    return render_template('create_pg.html')


@app.route('/manager/pg/<int:pg_id>/payment-settings', methods=['GET', 'POST'])
@login_required
@role_required('manager')
@manager_mfa_required
def payment_settings(pg_id):
    pg = PG.query.get_or_404(pg_id)
    if pg.manager_id != current_user.id:
        flash('Invalid PG access.', 'danger')
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        pg.upi_id = request.form.get('upi_id')
        pg.bank_account = request.form.get('bank_account')
        pg.ifsc = request.form.get('ifsc')
        pg.qr_code_url = request.form.get('qr_code_url')
        db.session.commit()
        flash('Payment settings updated.', 'success')
    return render_template('payment_settings.html', pg=pg)


@app.route('/manager/flat/create', methods=['POST'])
@login_required
@role_required('manager')
def create_flat():
    pg = PG.query.get_or_404(int(request.form['pg_id']))
    if pg.manager_id != current_user.id:
        flash('Invalid PG.', 'danger')
        return redirect(url_for('dashboard'))
    db.session.add(Flat(name=request.form['name'], floor_number=int(request.form['floor_number']), pg_id=pg.id))
    db.session.commit()
    flash('Flat created.', 'success')
    return redirect(url_for('dashboard'))


@app.route('/manager/room/create', methods=['POST'])
@login_required
@role_required('manager')
def create_room():
    flat = Flat.query.get_or_404(int(request.form['flat_id']))
    pg = PG.query.get(flat.pg_id)
    if pg.manager_id != current_user.id:
        flash('Invalid flat.', 'danger')
        return redirect(url_for('dashboard'))
    db.session.add(Room(
        name=request.form['name'],
        sharing_type=request.form['sharing_type'],
        capacity=int(request.form['capacity']),
        rent_per_bed=float(request.form['rent_per_bed']),
        flat_id=flat.id,
    ))
    db.session.commit()
    flash('Room created.', 'success')
    return redirect(url_for('dashboard'))


@app.route('/manager/customer/create', methods=['GET', 'POST'])
@login_required
@role_required('manager')
def create_customer():
    pgs = PG.query.filter_by(manager_id=current_user.id).all()
    flats = Flat.query.join(PG, PG.id == Flat.pg_id).filter(PG.manager_id == current_user.id).all()
    rooms = Room.query.join(Flat, Flat.id == Room.flat_id).join(PG, PG.id == Flat.pg_id).filter(PG.manager_id == current_user.id).all()
    if request.method == 'POST':
        if User.query.filter((User.username == request.form['username']) | (User.email == request.form['email']) | (User.mobile == request.form.get('mobile'))).first():
            flash('Customer login identity already exists.', 'danger')
            return redirect(url_for('create_customer'))

        user = User(username=request.form['username'], email=request.form['email'], mobile=request.form.get('mobile') or None, role='customer', approved=True)
        user.set_password(request.form['password'])
        db.session.add(user)
        db.session.flush()

        pg_id = int(request.form['pg_id'])
        room_id = int(request.form['room_id']) if request.form.get('room_id') else None
        if room_id:
            room = Room.query.get_or_404(room_id)
            flat = Flat.query.get_or_404(room.flat_id)
            if flat.pg_id != pg_id:
                flash('Selected room does not belong to selected PG.', 'danger')
                return redirect(url_for('create_customer'))

        profile = CustomerProfile(
            user_id=user.id,
            manager_id=current_user.id,
            pg_id=pg_id,
            room_id=room_id,
            full_name=request.form['full_name'],
            permanent_address=request.form['permanent_address'],
            emergency_contact=request.form['emergency_contact'],
            company=request.form.get('company'),
            with_food='with_food' in request.form,
            deposit_amount=float(request.form.get('deposit_amount') or 0),
            status='admitted',
            join_date=date.today(),
        )
        db.session.add(profile)
        db.session.commit()
        flash('Customer admitted.', 'success')
        return redirect(url_for('dashboard'))
    return render_template('create_customer.html', pgs=pgs, flats=flats, rooms=rooms)


@app.route('/manager/customer/<int:profile_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('manager')
def edit_customer(profile_id):
    profile = CustomerProfile.query.get_or_404(profile_id)
    if profile.manager_id != current_user.id:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        profile.company = request.form.get('company')
        profile.with_food = 'with_food' in request.form
        profile.deposit_amount = float(request.form.get('deposit_amount') or 0)
        db.session.commit()
        flash('Customer updated.', 'success')
        return redirect(url_for('dashboard'))
    return render_template('edit_customer.html', profile=profile)


@app.route('/manager/customer/<int:profile_id>/exit', methods=['POST'])
@login_required
@role_required('manager')
def exit_customer(profile_id):
    profile = CustomerProfile.query.get_or_404(profile_id)
    if profile.manager_id != current_user.id:
        return redirect(url_for('dashboard'))
    profile.status = 'exited'
    profile.exit_date = date.today()
    db.session.commit()
    flash('Customer marked exited.', 'success')
    return redirect(url_for('dashboard'))


@app.route('/manager/rent/create', methods=['POST'])
@login_required
@role_required('manager')
def create_rent():
    profile = CustomerProfile.query.get_or_404(int(request.form['customer_id']))
    if profile.manager_id != current_user.id or profile.status != 'admitted':
        flash('Invoice allowed only for your admitted customers.', 'danger')
        return redirect(url_for('dashboard'))
    room = Room.query.get(profile.room_id) if profile.room_id else None
    pg = PG.query.get(profile.pg_id)
    rent = room.rent_per_bed if room else 0
    food = pg.food_charge if profile.with_food else 0
    invoice = RentInvoice(customer_id=profile.id, month_label=request.form['month_label'], rent_amount=rent, food_amount=food, total_amount=rent + food)
    db.session.add(invoice)
    db.session.commit()
    flash('Invoice created.', 'success')
    return redirect(url_for('dashboard'))




@app.route('/manager/invoice/<int:invoice_id>/mark-paid', methods=['POST'])
@login_required
@role_required('manager')
def manager_mark_paid(invoice_id):
    invoice = RentInvoice.query.get_or_404(invoice_id)
    profile = CustomerProfile.query.get_or_404(invoice.customer_id)
    if profile.manager_id != current_user.id:
        flash('Invalid invoice access.', 'danger')
        return redirect(url_for('dashboard'))
    invoice.paid = True
    db.session.commit()
    flash('Invoice marked as paid by manager.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/customer/pay/<int:invoice_id>')
@login_required
@role_required('customer')
def customer_pay(invoice_id):
    invoice = RentInvoice.query.get_or_404(invoice_id)
    profile = CustomerProfile.query.filter_by(user_id=current_user.id).first()
    if not profile or invoice.customer_id != profile.id:
        return redirect(url_for('dashboard'))
    pg = PG.query.get(profile.pg_id)
    upi_deeplink = f"upi://pay?pa={pg.upi_id}&pn={pg.name}&am={invoice.total_amount}&tn=Rent-{invoice.month_label}" if pg.upi_id else None
    return render_template('pay_invoice.html', invoice=invoice, pg=pg, upi_deeplink=upi_deeplink)


@app.route('/customer/mark-paid/<int:invoice_id>', methods=['POST'])
@login_required
@role_required('customer')
def customer_mark_paid(invoice_id):
    invoice = RentInvoice.query.get_or_404(invoice_id)
    profile = CustomerProfile.query.filter_by(user_id=current_user.id).first()
    if profile and invoice.customer_id == profile.id:
        invoice.paid = True
        db.session.commit()
        flash('Payment marked as paid (demo flow).', 'success')
    return redirect(url_for('dashboard'))


@app.route('/manager/reports')
@login_required
@role_required('manager', 'admin')
def reports():
    start = date(date.today().year, date.today().month, 1)
    if current_user.role == 'manager':
        new_customers = CustomerProfile.query.filter(CustomerProfile.manager_id == current_user.id, CustomerProfile.join_date >= start).all()
        paid_invoices = db.session.query(RentInvoice).join(CustomerProfile, RentInvoice.customer_id == CustomerProfile.id).filter(CustomerProfile.manager_id == current_user.id, RentInvoice.paid.is_(True)).all()
    else:
        new_customers = CustomerProfile.query.filter(CustomerProfile.join_date >= start).all()
        paid_invoices = RentInvoice.query.filter_by(paid=True).all()
    return render_template('reports.html', new_customers=new_customers, paid_invoices=paid_invoices)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(role='admin').first():
            admin = User(username='admin', email='admin@pgapp.com', mobile='9999999999', role='admin', approved=True)
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
    app.run(debug=True)
