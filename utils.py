import hashlib
import hmac
import json
import math
import os
import re
import time
from functools import wraps
from flask import request, jsonify, g

SECRET_KEY = os.getenv('SECRET_KEY', 'localfind-dev-secret-change-in-prod')

def _b64(data):
    import base64
    return base64.urlsafe_b64encode(data.encode()).decode().rstrip('=')

def _unb64(data):
    import base64
    pad = 4 - len(data) % 4
    if pad != 4:
        data += '=' * pad
    return base64.urlsafe_b64decode(data).decode()

def generate_token(shop_id, email):
    payload = json.dumps({'shop_id': shop_id, 'email': email, 'ts': int(time.time())})
    b64_payload = _b64(payload)
    sig = hmac.new(SECRET_KEY.encode(), b64_payload.encode(), hashlib.sha256).hexdigest()
    return f"{b64_payload}.{sig}"

def verify_token(token):
    try:
        b64_payload, sig = token.rsplit('.', 1)
        expected = hmac.new(SECRET_KEY.encode(), b64_payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(_unb64(b64_payload))
        if time.time() - payload['ts'] > 30 * 86400:
            return None
        return payload
    except Exception:
        return None

def hash_password(password):
    salt = os.urandom(16).hex()
    h = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 260000)
    return f"{salt}:{h.hex()}"

def check_password(password, stored):
    try:
        salt, h = stored.split(':')
        candidate = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 260000)
        return hmac.compare_digest(candidate.hex(), h)
    except Exception:
        return False

def require_shop_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get('Authorization', '')
        if not auth.startswith('Bearer '):
            return error('Login zaruri hai', 401)
        token = auth[7:]
        payload = verify_token(token)
        if not payload:
            return error('Token invalid ya expired', 401)
        g.shop_id = payload['shop_id']
        g.shop_email = payload['email']
        return f(*args, **kwargs)
    return decorated

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return R * 2 * math.asin(math.sqrt(a))

def shops_within_radius(shops, user_lat, user_lon, radius_km):
    result = []
    for s in shops:
        if s['latitude'] and s['longitude']:
            dist = haversine(user_lat, user_lon, s['latitude'], s['longitude'])
            if dist <= radius_km:
                result.append({**dict(s), 'distance_km': round(dist, 2)})
    result.sort(key=lambda x: x['distance_km'])
    return result

def success(data=None, message='', status=200):
    body = {'ok': True}
    if message:
        body['message'] = message
    if data is not None:
        body['data'] = data
    return jsonify(body), status

def error(message, status=400, details=None):
    body = {'ok': False, 'error': message}
    if details:
        body['details'] = details
    return jsonify(body), status

def validate_phone(phone):
    digits = re.sub(r'\D', '', phone)
    if len(digits) == 10 and digits[0] in '6789':
        return '91' + digits
    if len(digits) == 12 and digits.startswith('91'):
        return digits
    return None

def validate_pincode(pin):
    return bool(re.match(r'^\d{6}$', pin.strip()))

def sanitize_str(s, max_len=255):
    return str(s or '').strip()[:max_len]