"""
LocalFind — User / Request Routes

POST /api/requests/new          — user submits a search request
GET  /api/requests/:id          — poll request status + shop responses
GET  /api/requests/:id/responses — get all shop responses for a request (with prices)
POST /api/requests/:id/select   — user selects a shop → generates WA link
POST /api/requests/:id/cancel   — user cancels their request
"""

import json
from flask import Blueprint, request
from db.schema import get_db
from utils import (
    success, error, validate_phone, sanitize_str, shops_within_radius
)

requests_bp = Blueprint('requests', __name__, url_prefix='/api/requests')


# ══════════════════════════════════════════════════════════════════════════════
# CREATE A NEW REQUEST
# ══════════════════════════════════════════════════════════════════════════════

@requests_bp.route('/new', methods=['POST'])
def create_request():
    """
    User submits what they want. System:
      1. Saves the request
      2. Finds nearby registered shops within radius
      3. Returns list of notified shop IDs (WhatsApp notifications sent separately)
    """
    data = request.get_json(silent=True) or {}

    item_name   = sanitize_str(data.get('item_name', ''), 200)
    category    = sanitize_str(data.get('category', ''), 60)
    description = sanitize_str(data.get('description', ''), 500)
    user_phone_raw = str(data.get('user_phone', ''))
    user_name   = sanitize_str(data.get('user_name', 'Customer'), 80)
    latitude    = data.get('latitude')
    longitude   = data.get('longitude')
    radius_km   = float(data.get('radius_km', 5))
    city        = sanitize_str(data.get('city', 'jaipur'), 60).lower()

    # ── Validate ──────────────────────────────────────────────────────────
    errors = {}
    if not item_name:
        errors['item_name'] = 'Item ka naam zaruri hai'
    user_phone = validate_phone(user_phone_raw)
    if not user_phone:
        errors['user_phone'] = 'Valid WhatsApp number chahiye'
    if not latitude or not longitude:
        errors['location'] = 'Location (latitude/longitude) zaruri hai'
    if radius_km not in (2, 5, 10, 20):
        radius_km = 5

    if errors:
        return error('Kuch fields galat hain', 422, errors)

    db = get_db()
    try:
        # Upsert user
        db.execute("""
            INSERT INTO users (name, phone, latitude, longitude, city)
            VALUES (?,?,?,?,?)
            ON CONFLICT(phone) DO UPDATE SET
                name=excluded.name,
                latitude=excluded.latitude,
                longitude=excluded.longitude,
                city=excluded.city
        """, (user_name, user_phone, latitude, longitude, city))

        user = db.execute('SELECT id FROM users WHERE phone=?', (user_phone,)).fetchone()

        # Find nearby active shops in this city
        all_shops = db.execute("""
            SELECT id, shop_name, wa_primary, wa_backup, latitude, longitude
            FROM shops
            WHERE is_active=1 AND city=?
        """, (city,)).fetchall()

        nearby = shops_within_radius(all_shops, latitude, longitude, radius_km)
        notified_ids = [s['id'] for s in nearby]

        # Save the request
        cur = db.execute("""
            INSERT INTO requests
              (user_id, user_phone, item_name, category, description,
               latitude, longitude, radius_km, city, notified_shops)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (user['id'], user_phone, item_name, category, description,
              latitude, longitude, radius_km, city, json.dumps(notified_ids)))
        db.commit()

        request_id = cur.lastrowid

        # Create pending response rows for each notified shop
        for shop in nearby:
            db.execute("""
                INSERT OR IGNORE INTO responses (request_id, shop_id, status)
                VALUES (?,?, 'pending')
            """, (request_id, shop['id']))
        db.commit()

        return success({
            'request_id': request_id,
            'item_name': item_name,
            'notified_shops': len(nearby),
            'shops': [{'id': s['id'], 'name': s['shop_name'], 'distance_km': s['distance_km']} for s in nearby],
            'city': city,
            'radius_km': radius_km,
        }, f'{len(nearby)} nearby shops ko notification bheja gaya!', 201)

    except Exception as e:
        db.rollback()
        return error(f'Server error: {str(e)}', 500)
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════════════════════
# GET REQUEST STATUS
# ══════════════════════════════════════════════════════════════════════════════

@requests_bp.route('/<int:req_id>', methods=['GET'])
def get_request(req_id):
    """Poll endpoint — user checks if shops have replied."""
    user_phone_raw = request.args.get('phone', '')
    user_phone = validate_phone(user_phone_raw)

    db = get_db()
    try:
        req = db.execute('SELECT * FROM requests WHERE id=?', (req_id,)).fetchone()
        if not req:
            return error('Request nahi mila', 404)

        # Verify caller is the request owner
        if user_phone and req['user_phone'] != user_phone:
            return error('Yeh aapki request nahi hai', 403)

        # Count responses
        total_notified = len(json.loads(req['notified_shops'] or '[]'))
        resp_counts = db.execute("""
            SELECT status, COUNT(*) as cnt
            FROM responses WHERE request_id=?
            GROUP BY status
        """, (req_id,)).fetchall()

        counts = {r['status']: r['cnt'] for r in resp_counts}

        return success({
            'request': dict(req),
            'stats': {
                'total_notified': total_notified,
                'available':   counts.get('available', 0),
                'unavailable': counts.get('unavailable', 0),
                'pending':     counts.get('pending', 0),
                'locked':      counts.get('locked', 0),
            }
        })
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════════════════════
# GET SHOP RESPONSES (prices revealed here)
# ══════════════════════════════════════════════════════════════════════════════

@requests_bp.route('/<int:req_id>/responses', methods=['GET'])
def get_responses(req_id):
    """
    Returns all 'available' shop responses for a request.
    Price is shown — user must verify ownership via phone.
    """
    user_phone_raw = request.args.get('phone', '')
    user_phone = validate_phone(user_phone_raw)
    if not user_phone:
        return error('Phone number se verify karna padega', 401)

    db = get_db()
    try:
        req = db.execute('SELECT * FROM requests WHERE id=?', (req_id,)).fetchone()
        if not req:
            return error('Request nahi mila', 404)
        if req['user_phone'] != user_phone:
            return error('Yeh aapki request nahi hai', 403)

        responses = db.execute("""
            SELECT rs.id, rs.status, rs.price, rs.note, rs.replied_at,
                   s.id as shop_id, s.shop_name, s.category,
                   s.address, s.area, s.city,
                   s.wa_primary, s.rating, s.total_reviews,
                   s.open_time, s.close_time,
                   s.latitude as shop_lat, s.longitude as shop_lon
            FROM responses rs
            JOIN shops s ON s.id = rs.shop_id
            WHERE rs.request_id=?
              AND rs.status='available'
            ORDER BY rs.price ASC
        """, (req_id,)).fetchall()

        result = []
        for r in responses:
            row = dict(r)
            # Distance from request origin to shop
            if r['shop_lat'] and r['shop_lon']:
                from utils import haversine
                row['distance_km'] = round(
                    haversine(req['latitude'], req['longitude'], r['shop_lat'], r['shop_lon']), 2
                )
            result.append(row)

        return success({
            'request_id': req_id,
            'item_name': req['item_name'],
            'responses': result,
            'count': len(result),
        })
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════════════════════
# USER SELECTS A SHOP → WhatsApp link
# ══════════════════════════════════════════════════════════════════════════════

@requests_bp.route('/<int:req_id>/select', methods=['POST'])
def select_shop(req_id):
    """
    User picks a shop. Returns a WhatsApp deep-link with pre-filled order message.
    Also marks request as 'fulfilled'.
    """
    data = request.get_json(silent=True) or {}
    shop_id        = data.get('shop_id')
    user_phone_raw = str(data.get('user_phone', ''))
    user_phone     = validate_phone(user_phone_raw)

    if not shop_id:
        return error('shop_id zaruri hai', 422)
    if not user_phone:
        return error('Phone number zaruri hai', 422)

    db = get_db()
    try:
        req = db.execute('SELECT * FROM requests WHERE id=?', (req_id,)).fetchone()
        if not req or req['user_phone'] != user_phone:
            return error('Request nahi mila ya access denied', 403)

        resp = db.execute("""
            SELECT rs.price, rs.note, s.shop_name, s.wa_primary, s.area
            FROM responses rs
            JOIN shops s ON s.id = rs.shop_id
            WHERE rs.request_id=? AND rs.shop_id=? AND rs.status='available'
        """, (req_id, shop_id)).fetchone()

        if not resp:
            return error('Yeh shop available nahi hai', 404)

        # Build WhatsApp message
        price_str = f"₹{int(resp['price'])}" if resp['price'] else 'price unconfirmed'
        wa_msg = (
            f"Namaste! Main LocalFind se aa raha hoon 🙏\n\n"
            f"*Item:* {req['item_name']}\n"
            f"*Quoted Price:* {price_str}\n"
            f"*Request ID:* #{req_id}\n\n"
            f"Kya yeh abhi bhi available hai? Main aane wala hoon!"
        )
        import urllib.parse
        wa_link = f"https://wa.me/{resp['wa_primary']}?text={urllib.parse.quote(wa_msg)}"

        # Mark request fulfilled
        db.execute("UPDATE requests SET status='fulfilled' WHERE id=?", (req_id,))
        db.commit()

        return success({
            'shop_name': resp['shop_name'],
            'shop_area': resp['area'],
            'price': resp['price'],
            'wa_link': wa_link,
            'wa_number': resp['wa_primary'],
        }, 'WhatsApp link ready hai!')
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════════════════════
# CANCEL REQUEST
# ══════════════════════════════════════════════════════════════════════════════

@requests_bp.route('/<int:req_id>/cancel', methods=['POST'])
def cancel_request(req_id):
    data = request.get_json(silent=True) or {}
    user_phone = validate_phone(str(data.get('user_phone', '')))
    if not user_phone:
        return error('Phone number zaruri hai', 422)

    db = get_db()
    try:
        req = db.execute('SELECT * FROM requests WHERE id=?', (req_id,)).fetchone()
        if not req or req['user_phone'] != user_phone:
            return error('Request nahi mila', 403)
        if req['status'] != 'open':
            return error('Yeh request pehle se close hai', 409)

        db.execute("UPDATE requests SET status='cancelled' WHERE id=?", (req_id,))
        db.commit()
        return success(message='Request cancel ho gayi')
    finally:
        db.close()