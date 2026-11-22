import os
import sqlite3
import requests
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import math
from msp_db import init_msp_table, search_msp

init_msp_table()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your_secret_key_here')

DATA_GOV_API_KEY = os.environ.get('DATA_GOV_API_KEY', '579b464db66ec23bdd000001855a90af847c44ad7b3bff72cf6a7d6d')
MANDI_RESOURCE_ID = '9ef84268-d588-465a-a308-a864a43d0070'

WEATHER_CODE_LABELS = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Foggy",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    80: "Rain showers",
    95: "Thunderstorm",
}


def get_db_connection():
    conn = sqlite3.connect('farmup.db')
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            mobile TEXT UNIQUE NOT NULL,
            state TEXT NOT NULL,
            district TEXT NOT NULL,
            village_town TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mandi_prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            state TEXT NOT NULL,
            district TEXT NOT NULL,
            market TEXT NOT NULL,
            commodity TEXT NOT NULL,
            variety TEXT,
            arrival_date TEXT,
            min_price TEXT,
            max_price TEXT,
            modal_price TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(state, district, market, commodity, variety)
        )
    ''')

    conn.commit()
    conn.close()


def haversine_km(lat1, lon1, lat2, lon2):
    radius_km = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius_km * math.asin(math.sqrt(a))


def geocode_place(query, state=""):
    if not query:
        return None
    resp = requests.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": query, "count": 5, "countryCode": "IN", "format": "json"},
        timeout=6,
    )
    resp.raise_for_status()
    results = resp.json().get("results") or []
    if not results:
        return None
    if state:
        for item in results:
            if state.lower() in str(item.get("admin1", "")).lower():
                return item
    return results[0]

FARMER_SCHEMES = [
    {
        "id": "pm-kisan",
        "name": "PM-KISAN (Pradhan Mantri Kisan Samman Nidhi)",
        "category": "income-risk",
        "category_label": "Income, Credit & Insurance",
        "summary": "Direct income support transferred to eligible landholding farmer families in three installments per year.",
        "key_points": "Supports beneficiary registration, e-KYC updates, and status tracking via the official portal.",
        "portal_label": "Open PM-KISAN Portal",
        "official_url": "https://pmkisan.gov.in/"
    },
    {
        "id": "pmfby",
        "name": "PMFBY (Pradhan Mantri Fasal Bima Yojana)",
        "category": "income-risk",
        "category_label": "Income, Credit & Insurance",
        "summary": "Crop insurance coverage against yield and weather risks with a premium calculator and crop-loss reporting channels.",
        "key_points": "Check state enrollment rules (some states use dedicated state portals) before submitting online.",
        "portal_label": "Open PMFBY Portal",
        "official_url": "https://pmfby.gov.in/"
    },
    {
        "id": "pm-aasha",
        "name": "PM-AASHA & Price / Procurement Support",
        "category": "procurement",
        "category_label": "MSP & Procurement",
        "summary": "Supports remunerative prices for farmers and notified agricultural produce procurement/price mechanisms.",
        "key_points": "Active procurement windows and agency registration depend on state notifications and crop coverage.",
        "portal_label": "View on India.gov.in",
        "official_url": "https://www.india.gov.in/my-government/documents/details/pradhan-mantri-annadata-aay-sanrakshan-abhiyan-pm-aasha-scheme"
    },
    {
        "id": "pm-kusum-irrigation",
        "name": "PM-KUSUM & Solar / Irrigation Support",
        "category": "water-soil",
        "category_label": "Irrigation & Soil",
        "summary": "Supports solarized agricultural pumps, decentralized solar capacity, and state-level nodal application tracking.",
        "key_points": "Applications and district nodal contacts are managed through state nodal agencies (e.g., UP nodal portal for Uttar Pradesh).",
        "portal_label": "Open UP PM-KUSUM Nodal Portal",
        "official_url": "https://pmkusum.up.gov.in/UP/contact.html"
    },
    {
        "id": "myscheme-agri-hub",
        "name": "All Central & State Agriculture Schemes (myScheme)",
        "category": "digital",
        "category_label": "Scheme Directory & Advisory",
        "summary": "Browse central and state agricultural schemes by state, crop, farmer category, eligibility criteria, and required documents.",
        "key_points": "Helpful when you want a broader directory across states beyond a single scheme portal.",
        "portal_label": "Browse myScheme Agriculture",
        "official_url": "https://www.myscheme.gov.in/search/category/Agriculture,Rural%20&%20Environment"
    }
]

@app.route('/')
def home():
    return render_template('Home.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form.get('fullname')
        mobile = request.form.get('mobile')
        state = request.form.get('state')
        district = request.form.get('district')
        village_town = request.form.get('village_town')

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute('''
                INSERT INTO users (full_name, mobile, state, district, village_town)
                VALUES (?, ?, ?, ?, ?)
            ''', (full_name, mobile, state, district, village_town))

            user_id = cursor.lastrowid
            conn.commit()
            conn.close()

            session['user_id'] = user_id
            session['user_name'] = full_name
            session['district'] = district
            session['state'] = state

            return redirect(url_for('home'))

        except sqlite3.IntegrityError:
            return render_template(
                'register.html',
                error="This mobile number is already registered. Please login or use a different number.",
                form_data={
                    'fullname': full_name,
                    'mobile': mobile,
                    'state': state,
                    'district': district,
                    'village_town': village_town
                }
            )

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        mobile = request.form.get('mobile')

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE mobile = ?', (mobile,)).fetchone()
        conn.close()

        if user:
            session['user_id'] = user['id']
            session['user_name'] = user['full_name']
            session['district'] = user['district']
            session['state'] = user['state']

            return redirect(url_for('home'))
        else:
            return render_template(
                'login.html',
                error="Mobile number not registered. Please sign up first.",
                mobile_entered=mobile
            )

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))


@app.route('/admin/users')
def view_users():
    conn = get_db_connection()
    users = conn.execute('SELECT * FROM users').fetchall()
    conn.close()

    html = "<h2>Registered Farmers</h2><table border='1'><tr><th>ID</th><th>Name</th><th>Mobile</th><th>State</th><th>District</th><th>Village/Town</th></tr>"
    for user in users:
        html += f"<tr><td>{user['id']}</td><td>{user['full_name']}</td><td>{user['mobile']}</td><td>{user['state']}</td><td>{user['district']}</td><td>{user['village_town']}</td></tr>"
    html += "</table>"
    return html


@app.route('/priceEstimator', methods=['GET'])
def priceEstimator():
    return render_template("price_estimator.html")


@app.route('/api/pincode/<pincode>')
def api_pincode(pincode):
    cleaned = ''.join(ch for ch in pincode if ch.isdigit())
    if len(cleaned) != 6:
        return jsonify({"error": "Please enter a valid 6-digit PIN code."}), 400

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) FarmUp/1.0",
        "Accept": "application/json",
    }

    last_exc = None
    for _ in range(2):
        try:
            resp = requests.get(
                f"https://api.postalpincode.in/pincode/{cleaned}",
                headers=headers,
                timeout=6,
            )
            resp.raise_for_status()
            data = resp.json()

            if data and str(data[0].get("Status", "")).lower() == "success":
                offices = data[0].get("PostOffice") or []
                if offices:
                    return jsonify({
                        "status": "success",
                        "pincode": cleaned,
                        "district": offices[0].get("District", ""),
                        "state": offices[0].get("State", ""),
                        "post_offices": [
                            {
                                "name": po.get("Name", ""),
                                "branch_type": po.get("BranchType", ""),
                                "block": po.get("Block", ""),
                            }
                            for po in offices
                        ],
                    })

            return jsonify({"status": "error", "message": "PIN code not found."}), 404

        except requests.RequestException as exc:
            last_exc = exc

    return jsonify({"status": "error", "message": f"Postal service unavailable: {last_exc}"}), 502


@app.route('/api/weather')
def api_weather():
    district = request.args.get('district', '').strip()
    state = request.args.get('state', '').strip()

    if not district:
        return jsonify({"error": "District is required."}), 400

    try:
        geo_resp = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": district, "count": 5, "countryCode": "IN", "format": "json"},
            timeout=6,
        )
        geo_resp.raise_for_status()
        results = geo_resp.json().get("results") or []

        if not results:
            return jsonify({"error": "Location coordinates not found."}), 404

        chosen = results[0]
        if state:
            for item in results:
                if state.lower() in str(item.get("admin1", "")).lower():
                    chosen = item
                    break

        lat = chosen["latitude"]
        lon = chosen["longitude"]

        wx_resp = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,weather_code",
                "timezone": "Asia/Kolkata",
            },
            timeout=6,
        )
        wx_resp.raise_for_status()
        current = wx_resp.json().get("current") or {}

        temp = current.get("temperature_2m")
        humidity = current.get("relative_humidity_2m")
        code = current.get("weather_code", 0)
        condition = WEATHER_CODE_LABELS.get(code, "Current weather")

        return jsonify({
            "district": district,
            "state": state or chosen.get("admin1", ""),
            "temperature": round(temp) if temp is not None else None,
            "humidity": humidity,
            "condition": condition,
        })

    except requests.RequestException as exc:
        return jsonify({"error": f"Weather service unavailable: {exc}"}), 502


@app.route('/api/mandi-prices')
def api_mandi_prices():
    raw_crop = request.args.get('crop', '').strip()
    district = request.args.get('district', '').strip()
    state = request.args.get('state', '').strip()

    commodity = raw_crop.split('/')[0].strip() if raw_crop else ''

    if not commodity or not district:
        return jsonify({"error": "Crop and district are required."}), 400

    params = {
        "api-key": DATA_GOV_API_KEY,
        "format": "json",
        "limit": 30,
        "filters[commodity]": commodity,
        "filters[district]": district,
    }
    if state:
        params["filters[state]"] = state

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        resp = requests.get(
            f"https://api.data.gov.in/resource/{MANDI_RESOURCE_ID}",
            params=params,
            timeout=5
        )
        resp.raise_for_status()
        records = resp.json().get("records", [])

        if records:
            formatted = []
            for row in records:
                item = {
                    "market": row.get("market", "Unknown Mandi"),
                    "district": row.get("district", district),
                    "state": row.get("state", state),
                    "variety": row.get("variety", "Standard"),
                    "arrival_date": row.get("arrival_date", "Latest"),
                    "min_price": row.get("min_price", "N/A"),
                    "max_price": row.get("max_price", "N/A"),
                    "modal_price": row.get("modal_price", "N/A"),
                }
                formatted.append(item)

                cursor.execute('''
                    INSERT INTO mandi_prices 
                        (state, district, market, commodity, variety, arrival_date, min_price, max_price, modal_price, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(state, district, market, commodity, variety) 
                    DO UPDATE SET 
                        arrival_date=excluded.arrival_date,
                        min_price=excluded.min_price,
                        max_price=excluded.max_price,
                        modal_price=excluded.modal_price,
                        updated_at=CURRENT_TIMESTAMP
                ''', (
                    item["state"], item["district"], item["market"], commodity,
                    item["variety"], item["arrival_date"], item["min_price"],
                    item["max_price"], item["modal_price"]
                ))

            conn.commit()
            conn.close()
            return jsonify({
                "source": "live_api",
                "commodity": commodity,
                "district": district,
                "mandis": formatted
            })

    except Exception as e:
        print(f"Live API unavailable ({e}), falling back to database...")

    cached_rows = cursor.execute('''
        SELECT market, district, state, variety, arrival_date, min_price, max_price, modal_price, updated_at
        FROM mandi_prices
        WHERE LOWER(commodity) = LOWER(?) AND LOWER(district) = LOWER(?)
        ORDER BY updated_at DESC
    ''', (commodity, district)).fetchall()
    conn.close()

    formatted_cache = [dict(row) for row in cached_rows]

    return jsonify({
        "source": "database_fallback",
        "commodity": commodity,
        "district": district,
        "mandis": formatted_cache
    })

@app.route('/api/market-distance')
def api_market_distance():
    user_lat_raw = request.args.get('user_lat', '').strip()
    user_lon_raw = request.args.get('user_lon', '').strip()
    market = request.args.get('market', '').strip()
    district = request.args.get('district', '').strip()
    state = request.args.get('state', '').strip()

    if not user_lat_raw or not user_lon_raw:
        return jsonify({"error": "user_lat and user_lon are required."}), 400
    if not (market or district):
        return jsonify({"error": "Target market or district is required."}), 400

    try:
        origin_lat = float(user_lat_raw)
        origin_lon = float(user_lon_raw)
        dest = geocode_place(market, state) or geocode_place(district, state)
        if not dest:
            return jsonify({"error": "Could not find coordinates for this market."}), 404

        straight_km = haversine_km(origin_lat, origin_lon, dest["latitude"], dest["longitude"])
        estimated_road_km = round(max(straight_km * 1.25, 1.0), 1)

        return jsonify({
            "destination": f"{dest.get('name', market or district)}, {dest.get('admin1', state)}".strip(", "),
            "distance_km": estimated_road_km,
            "straight_line_km": round(straight_km, 1),
            "distance_type": "estimated_road_from_gps",
        })
    except ValueError:
        return jsonify({"error": "Invalid latitude or longitude."}), 400
    except requests.RequestException as exc:
        return jsonify({"error": f"Geocoding lookup failed: {exc}"}), 502

@app.route('/other-services')
def other_services():
    return render_template('other_services.html', schemes=FARMER_SCHEMES)


@app.route('/api/msp')
def api_msp():
    crop = request.args.get('crop', '').strip()
    region = request.args.get('region', '').strip()

    if not crop:
        return jsonify({"error": "Please enter a crop name."}), 400

    try:
        records = search_msp(crop)
    except Exception as exc:
        return jsonify({"error": f"MSP lookup failed: {exc}"}), 500

    if not records:
        return jsonify({
            "found": False,
            "crop": crop,
            "region": region or "All India",
            "region_required": False,
            "message": f"No government MSP record found for '{crop}'. Not every crop has an official MSP—check daily mandi prices in the Price Estimator."
        }), 200

    region_required = any(r.get("region_required") for r in records)
    return jsonify({
        "found": True,
        "crop": crop,
        "region": region or "All India",
        "region_required": region_required,
        "records": records
    }), 200

if __name__ == '__main__':
    init_db()
    app.run(debug=False)