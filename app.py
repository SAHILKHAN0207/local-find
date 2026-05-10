"""
LocalFind — Main Flask Application
Run: python3 app.py
"""
import sys
sys.stdout.reconfigure(line_buffering=True)
import os
import sys
import json
from routes.shops import shops_bp
from routes.requests import requests_bp
from flask import Flask, jsonify, request

sys.path.insert(0, os.path.dirname(__file__))

from db.schema import init_db, get_db

app = Flask(__name__, static_folder='.', static_url_path='')
app.config['JSON_AS_ASCII'] = False

@app.after_request
def add_cors(response):
    response.headers['Access-Control-Allow-Origin']  = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    return response



app.register_blueprint(shops_bp)
app.register_blueprint(requests_bp)

@app.route('/test', methods=['POST'])
def test():
    data = request.form.get('From', 'NO DATA')
    return f"ok - got: {data}"

@app.route('/admin')
def admin_panel():
    return app.send_static_file('admin.html')

@app.route('/api/admin/shops', methods=['GET'])
def admin_get_shops():
    db = get_db()
    try:
        shops = db.execute('SELECT * FROM shops ORDER BY created_at DESC').fetchall()
        return jsonify({'ok': True, 'data': {'shops': [dict(s) for s in shops], 'count': len(shops)}})
    finally:
        db.close()

@app.route('/api/admin/shops/<int:shop_id>', methods=['DELETE'])
def admin_delete_shop(shop_id):
    db = get_db()
    try:
        db.execute('DELETE FROM shops WHERE id=?', (shop_id,))
        db.commit()
        return jsonify({'ok': True})
    finally:
        db.close()

@app.route('/api/admin/shops/<int:shop_id>/toggle', methods=['POST'])
def admin_toggle_shop(shop_id):
    db = get_db()
    try:
        shop = db.execute('SELECT is_active FROM shops WHERE id=?', (shop_id,)).fetchone()
        new_status = 0 if shop['is_active'] else 1
        db.execute('UPDATE shops SET is_active=? WHERE id=?', (new_status, shop_id))
        db.commit()
        return jsonify({'ok': True, 'is_active': new_status})
    finally:
        db.close()

@app.route('/api/admin/requests', methods=['GET'])
def admin_get_requests():
    db = get_db()
    try:
        reqs = db.execute('SELECT * FROM requests ORDER BY created_at DESC').fetchall()
        return jsonify({'ok': True, 'data': {'requests': [dict(r) for r in reqs], 'count': len(reqs)}})
    finally:
        db.close()

@app.route('/api/admin/requests/<int:req_id>', methods=['DELETE'])
def admin_delete_request(req_id):
    db = get_db()
    try:
        db.execute('DELETE FROM requests WHERE id=?', (req_id,))
        db.commit()
        return jsonify({'ok': True})
    finally:
        db.close()

@app.route('/api/health', methods=['GET'])
def health():
    db = get_db()
    try:
        shops_count = db.execute('SELECT COUNT(*) as c FROM shops WHERE is_active=1').fetchone()['c']
        reqs_count  = db.execute("SELECT COUNT(*) as c FROM requests WHERE status='open'").fetchone()['c']
    finally:
        db.close()
    return jsonify({
        'ok': True,
        'status': 'LocalFind backend chal raha hai ✅',
        'active_shops': shops_count,
        'open_requests': reqs_count,
        'version': '1.0.0'
    })

@app.route('/api', methods=['GET'])
def api_index():
    return jsonify({'name': 'LocalFind API', 'status': 'running'})

@app.route('/')
def home():
    return app.send_static_file('index.html')

@app.route('/shop-register')
def shop_register():
    return app.send_static_file('shop-register.html')

@app.route('/search')
def search():
    return app.send_static_file('search.html')

@app.errorhandler(404)
def not_found(e):
    return jsonify({'ok': False, 'error': ' we cannot find Route '}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({'ok': False, 'error': 'Server error '}), 500

if __name__ == '__main__':
    print("🚀 LocalFind Backend ")
    init_db()
    port = int(os.getenv('PORT', 5000))
    print(f"✅ Server chal raha hai → http://localhost:{port}")
    print(f"❤️  Health → http://localhost:{port}/api/health")
    print("─" * 50)
    app.run(host='0.0.0.0', port=port, debug=True)