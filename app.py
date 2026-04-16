import streamlit as st
import sqlite3
from geopy.distance import geodesic
from datetime import date
import random
from streamlit_geolocation import streamlit_geolocation

# ---------------- CONFIG ----------------
st.set_page_config(page_title="LuggageX", layout="wide")

# ---------------- DATABASE ----------------
conn = sqlite3.connect("database.db", check_same_thread=False)
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    password TEXT,
    role TEXT,
    location TEXT,
    phone TEXT)''')

c.execute('''CREATE TABLE IF NOT EXISTS requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    host TEXT,
    pickup TEXT,
    delivery TEXT,
    bags INTEGER,
    distance REAL,
    price REAL,
    status TEXT,
    payment_status TEXT,
    pickup_date TEXT,
    delivery_date TEXT,
    otp TEXT,
    pick_lat REAL,
    pick_lon REAL,
    host_lat REAL,
    host_lon REAL,
    rating INTEGER,
    review TEXT
)''')

conn.commit()

# ---------------- FUNCTIONS ----------------
city_coords = {
    "Visakhapatnam": (17.6868, 83.2185),
    "Vijayawada": (16.5062, 80.6480),
    "Guntur": (16.3067, 80.4365),
    "Tirupati": (13.6288, 79.4192),
    "Hyderabad": (17.3850, 78.4867),
    "Chennai": (13.0827, 80.2707),
    "Bangalore": (12.9716, 77.5946),
    "Mumbai": (19.0760, 72.8777),
    "Delhi": (28.7041, 77.1025)
}
cities = list(city_coords.keys())

def get_distance(c1, c2):
    return geodesic(city_coords[c1], city_coords[c2]).km

def price_calc(bags, dist):
    return bags * 40 + dist * 4

def generate_otp():
    return str(random.randint(1000, 9999))

# ---------------- SESSION ----------------
if "user" not in st.session_state:
    st.session_state.user = None

# ---------------- LOGIN ----------------
if st.session_state.user is None:
    st.title("🎒 LuggageX")

    opt = st.radio("Login/Signup", ["Login", "Signup"])
    u = st.text_input("Username")
    p = st.text_input("Password", type="password")

    if opt == "Signup":
        role = st.selectbox("Role", ["Customer", "Host"])
        loc = st.selectbox("Location", cities)
        ph = st.text_input("Phone")

        if st.button("Signup"):
            try:
                c.execute("INSERT INTO users VALUES (?,?,?,?,?)", (u, p, role, loc, ph))
                conn.commit()
                st.success("Account created")
            except:
                st.error("User exists")

    if opt == "Login":
        role = st.selectbox("Role", ["Customer", "Host"])
        if st.button("Login"):
            c.execute("SELECT * FROM users WHERE username=? AND password=? AND role=?", (u, p, role))
            res = c.fetchone()
            if res:
                st.session_state.user = res
                st.rerun()
            else:
                st.error("Invalid login")

# ---------------- MAIN ----------------
else:
    user, pw, role, loc, ph = st.session_state.user

    st.sidebar.write(f"{user} ({role})")
    page = st.sidebar.selectbox("Menu", ["Home", "Dashboard", "History", "Help Line"])

    if st.sidebar.button("Logout"):
        st.session_state.user = None
        st.rerun()

    # ---------------- CUSTOMER HOME ----------------
    if role == "Customer" and page == "Home":
        st.title("📦 Create Request")

        bags = st.number_input("Bags", 1)

        st.subheader("📍 Pickup Location")
        pickup_mode = st.radio("Choose Pickup Type", ["Select City", "Use My Location"])

        pick = None
        pick_lat = None
        pick_lon = None

        if pickup_mode == "Select City":
            pick = st.selectbox("Pickup Location", cities)

        else:
            st.info("Click allow location to fetch GPS")
            location = streamlit_geolocation()

            if location and location.get("latitude"):
                pick_lat = location["latitude"]
                pick_lon = location["longitude"]
                pick = "My Location"
                st.success("Location captured")
                st.map([{"lat": pick_lat, "lon": pick_lon}])

        drop = st.selectbox("Delivery Location", cities)

        pickup_date = st.date_input("Pickup Date", value=date.today())
        delivery_date = st.date_input("Delivery Date", value=date.today())

        if pick == "My Location" and pick_lat:
            drop_lat, drop_lon = city_coords[drop]
            dist = geodesic((pick_lat, pick_lon), (drop_lat, drop_lon)).km
        elif pick:
            dist = get_distance(pick, drop)
        else:
            dist = 0

        price = price_calc(bags, dist)

        st.info(f"📏 Distance: {dist:.2f} km | 💰 ₹{price:.2f}")

        if st.button("Pay & Request"):
            c.execute('''INSERT INTO requests 
            VALUES (NULL,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (user, "", pick, drop, bags, dist, price, "Pending", "Paid",
             str(pickup_date), str(delivery_date), "",
             pick_lat, pick_lon, None, None, None, None))
            conn.commit()
            st.success("Order placed!")

    # ---------------- HOST HOME ----------------
    if role == "Host" and page == "Home":
        st.title("📦 Requests")

        # earnings
        c.execute("SELECT SUM(price) FROM requests WHERE host=? AND status='Completed'", (user,))
        earnings = c.fetchone()[0] or 0
        st.success(f"💰 Total Earnings: ₹{earnings}")

        host_loc = streamlit_geolocation()
        host_lat = host_lon = None

        if host_loc and host_loc.get("latitude"):
            host_lat = host_loc["latitude"]
            host_lon = host_loc["longitude"]

        c.execute("SELECT * FROM requests")
        for r in c.fetchall():
            rid, cust, host, loc1, loc2, bags, dist, price, status, pay, pdate, ddate, otp, pick_lat, pick_lon, hlat, hlon, rating, review = r

            st.info(f"""
🆔 {rid} | 📦 {bags} bags  
📍 {loc1} → {loc2}  
📏 {dist:.2f} km | 💰 ₹{price}  
📌 Status: {status}
""")

            if status == "Pending":
                if st.button(f"Accept {rid}"):
                    c.execute("UPDATE requests SET host=?, status='Accepted', host_lat=?, host_lon=? WHERE id=?",
                              (user, host_lat, host_lon, rid))
                    conn.commit()
                    st.rerun()

            if status == "Accepted" and host == user:
                if st.button(f"Mark Delivered {rid}"):
                    new_otp = generate_otp()
                    c.execute("UPDATE requests SET status='OTP', otp=? WHERE id=?", (new_otp, rid))
                    conn.commit()
                    st.success("OTP sent to customer")
                    st.rerun()

            if status == "OTP" and host == user:
                entered = st.text_input(f"Enter OTP {rid}", key=rid)
                if st.button(f"Verify {rid}"):
                    if entered == otp:
                        c.execute("UPDATE requests SET status='Completed', payment_status='Released' WHERE id=?", (rid,))
                        conn.commit()
                        st.success("Delivery completed ✅")
                        st.rerun()
                    else:
                        st.error("Wrong OTP")

            # ⭐ SHOW RATING
            if rating:
                st.write(f"⭐ Rating: {rating}/5")
                if review:
                    st.write(f"📝 {review}")

    # ---------------- CUSTOMER DASHBOARD ----------------
    if role == "Customer" and page == "Dashboard":
        st.title("📊 My Orders")

        c.execute("SELECT * FROM requests WHERE username=?", (user,))
        for r in c.fetchall():
            rid, cust, host, loc1, loc2, bags, dist, price, status, pay, pdate, ddate, otp, pick_lat, pick_lon, hlat, hlon, rating, review = r

            st.info(f"""
🆔 Order {rid}  
📍 {loc1} → {loc2}  
📦 {bags} bags | 💰 ₹{price}  
📌 Status: {status}
""")

            if status == "OTP":
                st.warning(f"🔐 Your OTP: {otp}")

            # ⭐ RATE HOST
            if status == "Completed" and rating is None:
                st.subheader(f"Rate Delivery {rid}")
                stars = st.slider("Rating", 1, 5, key=f"rate{rid}")
                text = st.text_input("Review", key=f"rev{rid}")

                if st.button(f"Submit Rating {rid}"):
                    c.execute("UPDATE requests SET rating=?, review=? WHERE id=?",
                              (stars, text, rid))
                    conn.commit()
                    st.success("Thanks for your feedback!")
                    st.rerun()

            if hlat and hlon:
                st.map([{"lat": hlat, "lon": hlon}])

    # ---------------- HISTORY ----------------
    if page == "History":
        st.title("📜 History")

        c.execute("SELECT * FROM requests")
        for r in c.fetchall():
            rid, cust, host, loc1, loc2, bags, dist, price, status, pay, pdate, ddate, otp, *_ = r

            st.success(f"""
🆔 {rid} | 👤 {cust} → 🚚 {host}  
📍 {loc1} → {loc2}  
📦 {bags} bags | 💰 ₹{price}  
📅 {pdate} → {ddate}  
📌 Status: {status}
""")

    # ---------------- HELP ----------------
    if page == "Help Line":
        st.title("🆘 Help")
        st.write("📞 +91 9876543210")