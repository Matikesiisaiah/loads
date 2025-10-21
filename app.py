import os
from datetime import datetime, timedelta
from flask import Flask, render_template, redirect, url_for, request, flash, session, abort, jsonify
from flask_login import LoginManager, login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Load, Truck, Booking, Message, Favorite
from forms import RegistrationForm, LoginForm, LoadForm, TruckForm, SearchForm, MessageForm
from math import radians, sin, cos, asin, sqrt

def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///loadboard.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    login_manager = LoginManager(app)
    login_manager.login_view = "login"

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    with app.app_context():
        db.create_all()

    # Utility: Haversine distance (km)
    def haversine(lat1, lon1, lat2, lon2):
        if None in (lat1, lon1, lat2, lon2):
            return None
        R = 6371.0
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = sin(dlat/2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        return R * c

    @app.route("/")
    def index():
        q_loads = Load.query.order_by(Load.created_at.desc()).limit(10).all()
        q_trucks = Truck.query.order_by(Truck.created_at.desc()).limit(10).all()
        return render_template("index.html", loads=q_loads, trucks=q_trucks)

    # Auth
    @app.route("/register", methods=["GET","POST"])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        form = RegistrationForm()
        if form.validate_on_submit():
            if User.query.filter_by(email=form.email.data.lower()).first():
                flash("Email already registered.", "warning")
                return redirect(url_for("login"))
            user = User(
                name=form.name.data.strip(),
                email=form.email.data.lower(),
                role=form.role.data,
            )
            user.password_hash = generate_password_hash(form.password.data)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash("Welcome aboard!", "success")
            return redirect(url_for("dashboard"))
        return render_template("auth/register.html", form=form)

    @app.route("/login", methods=["GET","POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        form = LoginForm()
        if form.validate_on_submit():
            user = User.query.filter_by(email=form.email.data.lower()).first()
            if user and check_password_hash(user.password_hash, form.password.data):
                login_user(user, remember=True)
                flash("Logged in.", "success")
                return redirect(url_for("dashboard"))
            flash("Invalid credentials.", "danger")
        return render_template("auth/login.html", form=form)

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        flash("Logged out.", "info")
        return redirect(url_for("index"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        loads = Load.query.filter_by(owner_id=current_user.id).order_by(Load.created_at.desc()).all() if current_user.is_shipper else []
        trucks = Truck.query.filter_by(owner_id=current_user.id).order_by(Truck.created_at.desc()).all() if current_user.is_carrier else []
        bookings = Booking.query.filter((Booking.shipper_id==current_user.id)|(Booking.carrier_id==current_user.id)).order_by(Booking.created_at.desc()).all()
        favs = Favorite.query.filter_by(user_id=current_user.id).all()
        return render_template("dashboard.html", loads=loads, trucks=trucks, bookings=bookings, favs=favs)

    # Loads CRUD
    @app.route("/loads")
    def loads():
        form = SearchForm(request.args)
        query = Load.query
        if form.origin_city.data:
            query = query.filter(Load.origin_city.ilike(f"%{form.origin_city.data.strip()}%"))
        if form.dest_city.data:
            query = query.filter(Load.dest_city.ilike(f"%{form.dest_city.data.strip()}%"))
        if form.earliest_date.data:
            query = query.filter(Load.pickup_date >= form.earliest_date.data)
        if form.latest_date.data:
            query = query.filter(Load.pickup_date <= form.latest_date.data)
        items = query.order_by(Load.created_at.desc()).all()
        return render_template("loads/list.html", loads=items, form=form)

    @app.route("/loads/new", methods=["GET","POST"])
    @login_required
    def loads_new():
        if not current_user.is_shipper:
            flash("Only shippers can post loads.", "warning")
            return redirect(url_for("loads"))
        form = LoadForm()
        if form.validate_on_submit():
            load = Load(
                owner_id=current_user.id,
                title=form.title.data.strip(),
                origin_city=form.origin_city.data.strip(),
                origin_lat=form.origin_lat.data,
                origin_lon=form.origin_lon.data,
                dest_city=form.dest_city.data.strip(),
                dest_lat=form.dest_lat.data,
                dest_lon=form.dest_lon.data,
                weight_kg=form.weight_kg.data,
                equipment=form.equipment.data.strip(),
                pickup_date=form.pickup_date.data,
                price_offer=form.price_offer.data,
                notes=form.notes.data.strip() if form.notes.data else None
            )
            db.session.add(load)
            db.session.commit()
            flash("Load posted.", "success")
            return redirect(url_for("loads"))
        return render_template("loads/new.html", form=form)

    @app.route("/loads/<int:load_id>")
    def load_detail(load_id):
        load = Load.query.get_or_404(load_id)
        distance_map = []
        trucks = Truck.query.all()
        for t in trucks:
            d = haversine(load.origin_lat or 0, load.origin_lon or 0, t.current_lat or 0, t.current_lon or 0)
            distance_map.append((t, d))
        distance_map.sort(key=lambda x: (x[1] if x[1] is not None else 1e9))
        return render_template("loads/detail.html", load=load, nearby=distance_map[:10])

    @app.route("/loads/<int:load_id>/favorite")
    @login_required
    def favorite_load(load_id):
        load = Load.query.get_or_404(load_id)
        fav = Favorite.query.filter_by(user_id=current_user.id, load_id=load.id).first()
        if fav:
            db.session.delete(fav)
            db.session.commit()
            flash("Removed from favorites.", "info")
        else:
            db.session.add(Favorite(user_id=current_user.id, load_id=load.id))
            db.session.commit()
            flash("Saved to favorites.", "success")
        return redirect(url_for("load_detail", load_id=load.id))

    # Trucks CRUD
    @app.route("/trucks")
    def trucks():
        items = Truck.query.order_by(Truck.created_at.desc()).all()
        return render_template("trucks/list.html", trucks=items)

    @app.route("/trucks/new", methods=["GET","POST"])
    @login_required
    def trucks_new():
        if not current_user.is_carrier:
            flash("Only carriers can list trucks.", "warning")
            return redirect(url_for("trucks"))
        form = TruckForm()
        if form.validate_on_submit():
            truck = Truck(
                owner_id=current_user.id,
                plate=form.plate.data.strip(),
                equipment=form.equipment.data.strip(),
                capacity_kg=form.capacity_kg.data,
                current_city=form.current_city.data.strip(),
                current_lat=form.current_lat.data,
                current_lon=form.current_lon.data,
                available_date=form.available_date.data
            )
            db.session.add(truck)
            db.session.commit()
            flash("Truck listed.", "success")
            return redirect(url_for("trucks"))
        return render_template("trucks/new.html", form=form)

    @app.route("/match", methods=["GET"])
    def match():
        # Simple matching by equipment and radius from load origin to truck current location
        form = SearchForm(request.args)
        matches = []
        for load in Load.query.all():
            for truck in Truck.query.filter(Truck.equipment.ilike(f"%{load.equipment}%")).all():
                dist = None
                if load.origin_lat and truck.current_lat:
                    dist = haversine(load.origin_lat, load.origin_lon, truck.current_lat, truck.current_lon)
                # Apply optional radius filter
                within = True
                if form.radius_km.data:
                    within = dist is None or dist <= form.radius_km.data
                if within:
                    matches.append((load, truck, dist))
        # sort by distance then pickup date
        matches.sort(key=lambda x: (x[2] if x[2] is not None else 1e9, x[0].pickup_date or datetime.utcnow()))
        return render_template("match.html", matches=matches, form=form)

    @app.route("/book/<int:load_id>/<int:truck_id>", methods=["POST"])
    @login_required
    def book(load_id, truck_id):
        load = Load.query.get_or_404(load_id)
        truck = Truck.query.get_or_404(truck_id)
        if not (current_user.is_shipper or current_user.is_admin):
            flash("Only shippers can book trucks.", "warning")
            return redirect(url_for("load_detail", load_id=load.id))
        if Booking.query.filter_by(load_id=load.id).first():
            flash("This load is already booked.", "warning")
            return redirect(url_for("load_detail", load_id=load.id))
        carrier_id = truck.owner_id
        booking = Booking(load_id=load.id, truck_id=truck.id, shipper_id=current_user.id, carrier_id=carrier_id, status="pending")
        db.session.add(booking)
        db.session.commit()
        flash("Booking requested. Carrier has been notified.", "success")
        return redirect(url_for("booking_detail", booking_id=booking.id))

    @app.route("/bookings/<int:booking_id>", methods=["GET","POST"])
    @login_required
    def booking_detail(booking_id):
        booking = Booking.query.get_or_404(booking_id)
        if current_user.id not in (booking.shipper_id, booking.carrier_id) and not current_user.is_admin:
            abort(403)
        form = MessageForm()
        if form.validate_on_submit():
            msg = Message(booking_id=booking.id, sender_id=current_user.id, text=form.text.data.strip())
            db.session.add(msg)
            db.session.commit()
            return redirect(url_for("booking_detail", booking_id=booking.id))
        messages = Message.query.filter_by(booking_id=booking.id).order_by(Message.created_at.asc()).all()
        return render_template("bookings/detail.html", booking=booking, messages=messages, form=form)

    @app.route("/bookings/<int:booking_id>/status", methods=["POST"])
    @login_required
    def booking_status(booking_id):
        booking = Booking.query.get_or_404(booking_id)
        if current_user.id not in (booking.shipper_id, booking.carrier_id) and not current_user.is_admin:
            abort(403)
        new_status = request.form.get("status")
        if new_status in {"pending","accepted","in_transit","delivered","cancelled"}:
            booking.status = new_status
            db.session.commit()
            flash("Status updated.", "success")
        return redirect(url_for("booking_detail", booking_id=booking.id))

    # Admin seed route
    @app.route("/admin/seed")
    @login_required
    def admin_seed():
        if not current_user.is_admin:
            abort(403)
        # Create demo loads/trucks if none
        import random
        if not Load.query.first():
            sample_loads = [
                ("Copper cathodes", "Lusaka", -15.3875, 28.3228, "Ndola", -12.9690, 28.6366, 24000, "Flatbed", datetime.utcnow().date() + timedelta(days=2), 2500.0),
                ("Maize bags", "Choma", -16.8067, 26.9533, "Lusaka", -15.3875, 28.3228, 18000, "Dry Van", datetime.utcnow().date() + timedelta(days=1), 1200.0),
                ("Fuel drums", "Kitwe", -12.8024, 28.2132, "Solwezi", -12.1730, 26.3894, 12000, "Tanker", datetime.utcnow().date() + timedelta(days=5), 3000.0),
            ]
            for s in sample_loads:
                db.session.add(Load(owner_id=current_user.id, title=s[0], origin_city=s[1], origin_lat=s[2], origin_lon=s[3],
                                    dest_city=s[4], dest_lat=s[5], dest_lon=s[6], weight_kg=s[7], equipment=s[8],
                                    pickup_date=s[9], price_offer=s[10]))
        if not Truck.query.first():
            sample_trucks = [
                ("ALB-1234", "Flatbed", 30000, "Lusaka", -15.3875, 28.3228),
                ("BCA-5678", "Dry Van", 20000, "Kafue", -15.7691, 28.1814),
                ("TRK-9999", "Tanker", 25000, "Ndola", -12.9690, 28.6366),
            ]
            for s in sample_trucks:
                db.session.add(Truck(owner_id=current_user.id, plate=s[0], equipment=s[1], capacity_kg=s[2], current_city=s[3], current_lat=s[4], current_lon=s[5], available_date=datetime.utcnow().date()))
        db.session.commit()
        flash("Demo data created.", "success")
        return redirect(url_for("dashboard"))

    # API endpoints (basic)
    @app.route("/api/loads")
    def api_loads():
        data = [l.to_dict() for l in Load.query.order_by(Load.created_at.desc()).all()]
        return jsonify(data)

    @app.route("/api/trucks")
    def api_trucks():
        data = [t.to_dict() for t in Truck.query.order_by(Truck.created_at.desc()).all()]
        return jsonify(data)

    return app
