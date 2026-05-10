"""
LocalFind — Shop Routes
POST /api/shops/register      — new shop registration
POST /api/shops/login         — shop owner login
GET  /api/shops/me            — get own shop profile
PUT  /api/shops/me            — update shop profile
GET  /api/shops/requests      — see open requests near shop
POST /api/shops/respond       — reply to a request (available/unavailable + price)
GET  /api/shops/responses     — history of shop's responses
"""
from thefuzz import process
import json
from flask import Blueprint, request, g
from db.schema import get_db
from utils import (
    success, error, require_shop_auth,
    hash_password, check_password, generate_token,
    validate_phone, validate_pincode, sanitize_str,
    haversine
)

shops_bp = Blueprint('shops', __name__, url_prefix='/api/shops')


# ══════════════════════════════════════════════════════════════════════════════
# REGISTER
# ══════════════════════════════════════════════════════════════════════════════

@shops_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json(silent=True) or {}

    # ── Required fields ──────────────────────────────────────────────────
    shop_name  = sanitize_str(data.get('shop_name'), 120)
    owner_name = sanitize_str(data.get('owner_name'), 80)
    category   = sanitize_str(data.get('category'), 50)
    address    = sanitize_str(data.get('address'), 300)
    area       = sanitize_str(data.get('area'), 100)
    city       = sanitize_str(data.get('city', 'jaipur'), 60).lower()
    pincode    = sanitize_str(data.get('pincode'), 6)
    wa_primary_raw = str(data.get('wa_primary', ''))
    password   = str(data.get('password', ''))

    errors = {}
    if not shop_name:   errors['shop_name']  = 'Dukaan ka naam zaruri hai'
    if not owner_name:  errors['owner_name'] = 'Owner ka naam zaruri hai'
    if not category:    errors['category']   = 'Category zaruri hai'
    if not address:     errors['address']    = 'Address zaruri hai'
    if not area:        errors['area']       = 'Area zaruri hai'
    if not validate_pincode(pincode): errors['pincode'] = 'Valid 6-digit pincode chahiye'

    wa_primary = validate_phone(wa_primary_raw)
    if not wa_primary:  errors['wa_primary'] = 'Valid WhatsApp number chahiye (10 digits)'

    if len(password) < 6: errors['password'] = 'Password kam se kam 6 characters ka hona chahiye'

    if errors:
        return error('Kuch fields galat hain', 422, errors)

    # ── Optional fields ──────────────────────────────────────────────────
    wa_backup_raw = str(data.get('wa_backup', ''))
    wa_backup = validate_phone(wa_backup_raw) if wa_backup_raw.strip() else None

    email       = sanitize_str(data.get('email', ''), 150) or None
    description = sanitize_str(data.get('description', ''), 500)
    open_time   = sanitize_str(data.get('open_time', ''), 20)
    close_time  = sanitize_str(data.get('close_time', ''), 20)
    latitude    = data.get('latitude')
    longitude   = data.get('longitude')

    password_hash = hash_password(password)

    db = get_db()
    try:
        # Check duplicate email
        if email:
            existing = db.execute('SELECT id FROM shops WHERE email=?', (email,)).fetchone()
            if existing:
                return error('Yeh email already registered hai', 409)

        # Check duplicate primary WA
        existing_wa = db.execute('SELECT id FROM shops WHERE wa_primary=?', (wa_primary,)).fetchone()
        if existing_wa:
            return error('Yeh WhatsApp number already registered hai', 409)

        cur = db.execute("""
            INSERT INTO shops
              (owner_name, shop_name, category, description,
               address, area, city, pincode, latitude, longitude,
               wa_primary, wa_backup, open_time, close_time,
               email, password_hash)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (owner_name, shop_name, category, description,
              address, area, city, pincode,
              latitude, longitude,
              wa_primary, wa_backup,
              open_time, close_time,
              email, password_hash))
        db.commit()

        shop_id = cur.lastrowid
        token = generate_token(shop_id, email or f'shop_{shop_id}')

        return success({
            'shop_id': shop_id,
            'shop_name': shop_name,
            'token': token,
            'wa_primary': wa_primary,
            'wa_backup': wa_backup,
        }, 'Dukaan successfully register ho gayi!', 201)

    except Exception as e:
        db.rollback()
        return error(f'Server error: {str(e)}', 500)
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════════════════════
# LOGIN
# ══════════════════════════════════════════════════════════════════════════════

@shops_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    email    = sanitize_str(data.get('email', ''))
    password = str(data.get('password', ''))

    if not email or not password:
        return error('Email aur password zaruri hai', 422)

    db = get_db()
    try:
        shop = db.execute('SELECT * FROM shops WHERE email=? AND is_active=1', (email,)).fetchone()
        if not shop or not check_password(password, shop['password_hash']):
            return error('Email ya password galat hai', 401)

        token = generate_token(shop['id'], email)
        return success({
            'shop_id': shop['id'],
            'shop_name': shop['shop_name'],
            'token': token,
            'wa_primary': shop['wa_primary'],
            'wa_backup': shop['wa_backup'],
        }, 'Login successful')
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════════════════════
# MY PROFILE
# ══════════════════════════════════════════════════════════════════════════════

@shops_bp.route('/me', methods=['GET'])
@require_shop_auth
def get_me():
    db = get_db()
    try:
        shop = db.execute("""
            SELECT id, owner_name, shop_name, category, description,
                   address, area, city, pincode, latitude, longitude,
                   wa_primary, wa_backup, open_time, close_time,
                   email, is_active, is_verified, rating, total_reviews, created_at
            FROM shops WHERE id=?
        """, (g.shop_id,)).fetchone()

        if not shop:
            return error('Shop nahi mili', 404)
        return success(dict(shop))
    finally:
        db.close()


@shops_bp.route('/me', methods=['PUT'])
@require_shop_auth
def update_me():
    data = request.get_json(silent=True) or {}
    db = get_db()
    try:
        shop = db.execute('SELECT * FROM shops WHERE id=?', (g.shop_id,)).fetchone()
        if not shop:
            return error('Shop nahi mili', 404)

        # Allow updating these fields
        fields = ['shop_name', 'owner_name', 'description', 'address',
                  'area', 'open_time', 'close_time', 'latitude', 'longitude']

        updates = {}
        for f in fields:
            if f in data:
                updates[f] = sanitize_str(data[f]) if isinstance(data[f], str) else data[f]

        # WhatsApp backup can be updated
        if 'wa_backup' in data:
            wa_b = validate_phone(str(data['wa_backup'])) if data['wa_backup'] else None
            updates['wa_backup'] = wa_b

        if not updates:
            return error('Koi field update ke liye nahi di', 422)

        set_clause = ', '.join(f"{k}=?" for k in updates)
        values = list(updates.values()) + [g.shop_id]
        db.execute(f"UPDATE shops SET {set_clause}, updated_at=datetime('now') WHERE id=?", values)
        db.commit()
        return success(message='Profile update ho gaya')
    except Exception as e:
        db.rollback()
        return error(str(e), 500)
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════════════════════
# OPEN REQUESTS NEAR THIS SHOP
# ══════════════════════════════════════════════════════════════════════════════

@shops_bp.route('/requests', methods=['GET'])
@require_shop_auth
def get_requests():
    """
    Returns open requests that:
    1. Are in the same city as the shop
    2. Are within the request's radius of the shop's location
    3. The shop hasn't already responded to
    """
    db = get_db()
    try:
        shop = db.execute(
            'SELECT * FROM shops WHERE id=?', (g.shop_id,)
        ).fetchone()
        if not shop:
            return error('Shop nahi mili', 404)

        # Fetch open requests in same city
        open_reqs = db.execute("""
            SELECT r.*, u.name as user_name
            FROM requests r
            LEFT JOIN users u ON u.id = r.user_id
            WHERE r.status='open'
              AND r.city=?
              AND r.expires_at > datetime('now')
            ORDER BY r.created_at DESC
        """, (shop['city'],)).fetchall()

        results = []
        for req in open_reqs:
            req = dict(req)

            # Check if shop already responded
            existing = db.execute(
                'SELECT status FROM responses WHERE request_id=? AND shop_id=?',
                (req['id'], g.shop_id)
            ).fetchone()
            if existing:
                req['my_response'] = existing['status']
            else:
                req['my_response'] = None

            # Distance from shop to request origin
            if shop['latitude'] and shop['longitude']:
                dist = haversine(
                    shop['latitude'], shop['longitude'],
                    req['latitude'], req['longitude']
                )
                req['distance_from_shop_km'] = round(dist, 2)
                # Skip if request is too far from shop
                if dist > req['radius_km'] + 1:
                    continue
            else:
                req['distance_from_shop_km'] = None

            results.append(req)

        return success({'requests': results, 'count': len(results)})
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════════════════════
# RESPOND TO A REQUEST
# ══════════════════════════════════════════════════════════════════════════════

@shops_bp.route('/respond', methods=['POST'])
@require_shop_auth
def respond_to_request():
    """
    Shop replies: available/unavailable + price.

    DUAL NUMBER LOGIC:
    - Both WA numbers receive notifications (handled by WhatsApp service).
    - When either number replies, this endpoint is called with replied_from.
    - If the OTHER number already replied first → this response is 'locked'
      and caller should send a "reply de diya" message to this number.
    - If this is the FIRST reply → save it, mark other shops' pending as 'locked'.
    """
    data = request.get_json(silent=True) or {}
    request_id  = data.get('request_id')
    status      = data.get('status')        # 'available' | 'unavailable'
    price       = data.get('price')         # float, INR
    note        = sanitize_str(data.get('note', ''), 300)
    replied_from = data.get('replied_from', 'primary')   # 'primary' | 'backup'
    wa_number   = data.get('wa_number', '')

    if not request_id:
        return error('request_id zaruri hai', 422)
    if status not in ('available', 'unavailable'):
        return error('status sirf "available" ya "unavailable" ho sakta hai', 422)
    if status == 'available' and not price:
        return error('Available batane par price bhi dena hoga', 422)

    db = get_db()
    try:
        # Verify request exists and is open
        req = db.execute(
            "SELECT * FROM requests WHERE id=? AND status='open'", (request_id,)
        ).fetchone()
        if not req:
            return error('Yeh request ab open nahi hai', 404)

        # Verify shop is registered and active
        shop = db.execute(
            'SELECT * FROM shops WHERE id=? AND is_active=1', (g.shop_id,)
        ).fetchone()
        if not shop:
            return error('Shop nahi mili', 404)

        # ── Check for existing response from THIS shop ────────────────────
        existing = db.execute(
            'SELECT * FROM responses WHERE request_id=? AND shop_id=?',
            (request_id, g.shop_id)
        ).fetchone()

        if existing:
            # ── DUAL NUMBER LOCK: other WA number of SAME shop already replied ──
            if existing['status'] in ('available', 'unavailable') and existing['replied_from'] and existing['replied_from'] != replied_from:
                # Second number trying to reply — send friendly lock response (not error)
                # WhatsApp bot will use this to send "reply de diya" message to this number
                return success({
                    'lock': True,
                    'already_replied_by': existing['replied_from'],
                    'message': f'Is request ka reply {existing["replied_from"]} number se pehle hi de diya gaya. Aapko kuch nahi karna.'
                }, 'Duplicate number — lock')

            # Same number trying to reply twice
            if existing['status'] in ('available', 'unavailable', 'locked'):
                return success({
                    'already_replied': True,
                    'status': existing['status'],
                    'message': 'Aapne is request par pehle hi reply kar diya hai.'
                }, 'Already replied')

        # ── Save the response ─────────────────────────────────────────────
        db.execute("""
            INSERT OR REPLACE INTO responses
              (request_id, shop_id, replied_from, wa_number, status, price, note, replied_at)
            VALUES (?,?,?,?,?,?,?, datetime('now'))
        """, (request_id, g.shop_id, replied_from, wa_number, status, price, note))
        db.commit()

        response_data = {
            'request_id': request_id,
            'shop_id': g.shop_id,
            'status': status,
            'price': price,
            'replied_from': replied_from,
        }

        # If available, also return user's contact for follow-up
        if status == 'available':
            response_data['user_phone'] = req['user_phone']
            response_data['item_name'] = req['item_name']

        return success(response_data, 'Reply save ho gaya! User ko notify kiya jayega.')

    except Exception as e:
        db.rollback()
        return error(f'Server error: {str(e)}', 500)
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════════════════════
# RESPONSE HISTORY
# ══════════════════════════════════════════════════════════════════════════════

@shops_bp.route('/responses', methods=['GET'])
@require_shop_auth
def get_response_history():
    db = get_db()
    try:
        rows = db.execute("""
            SELECT rs.*, rq.item_name, rq.city, rq.created_at as req_created
            FROM responses rs
            JOIN requests rq ON rq.id = rs.request_id
            WHERE rs.shop_id=?
            ORDER BY rs.created_at DESC
            LIMIT 50
        """, (g.shop_id,)).fetchall()
        return success({'responses': [dict(r) for r in rows], 'count': len(rows)})
    finally:
        db.close()

# ══════════════════════════════════════════════════════════════════════════════
# SEARCH SHOPS
# ══════════════════════════════════════════════════════════════════════════════

@shops_bp.route('/search', methods=['GET'])
def search_shops():
    q    = request.args.get('q', '').strip().lower()
    city = request.args.get('city', 'jaipur').lower()

    if not q:
        return error('Search query zaruri hai', 422)

    db = get_db()
    try:
        # Step 1: Saare products laao
        all_products = db.execute(
            "SELECT DISTINCT product, category FROM category_products"
        ).fetchall()

        product_list = [r['product'].lower() for r in all_products]

        # Step 2: Fuzzy match karo
        matches = process.extractBests(q, product_list, score_cutoff=70, limit=10)
        matched_products = [m[0] for m in matches]

        # Step 3: Matched products se categories nikalo
        cat_list = []
        if matched_products:
            placeholders_p = ','.join('?' * len(matched_products))
            cats = db.execute(
                f"SELECT DISTINCT category FROM category_products WHERE LOWER(product) IN ({placeholders_p})",
                matched_products
            ).fetchall()
            cat_list = [r['category'] for r in cats]

        # Step 4: Shops dhundho
        placeholders = ','.join('?' * len(cat_list)) if cat_list else None

        query = f"""
            SELECT id, shop_name, category, description,
                   address, area, rating, total_reviews, wa_primary
            FROM shops
            WHERE is_active=1 AND city=?
            AND (
                category LIKE ? OR shop_name LIKE ? OR
                description LIKE ?
                {('OR category IN (' + placeholders + ')') if placeholders else ''}
            )
            LIMIT 20
        """

        params = [city, f'%{q}%', f'%{q}%', f'%{q}%'] + cat_list
        rows = db.execute(query, params).fetchall()
        return success({'shops': [dict(r) for r in rows], 'count': len(rows)})
    finally:
        db.close()