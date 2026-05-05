import os
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()

ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
AUTH_TOKEN  = os.getenv('TWILIO_AUTH_TOKEN')
FROM_NUMBER = os.getenv('TWILIO_WHATSAPP_NUMBER')

client = Client(ACCOUNT_SID, AUTH_TOKEN)


def send_whatsapp(to_number, message):
    try:
        msg = client.messages.create(
            from_=FROM_NUMBER,
            to=f'whatsapp:+{to_number}',
            body=message
        )
        print(f"✅ Message sent to +{to_number}")
        return True
    except Exception as e:
        print(f"❌ Failed: {str(e)}")
        return False


def notify_shop(shop, request_id, item_name, distance_km):
    message = (
        f"🔔 *New LocalFind Request!*\n\n"
        f"*Item:* {item_name}\n"
        f"*Request ID:* #{request_id}\n"
        f"*Distance:* {distance_km} km\n\n"
        f"Reply with:\n"
        f"✅ *YES {request_id}* — available\n"
        f"❌ *NO {request_id}* — not available\n"
        f"💰 *PRICE {request_id} 25000* — set price"
    )
    send_whatsapp(shop['wa_primary'], message)
    if shop.get('wa_backup'):
        send_whatsapp(shop['wa_backup'], message)


def notify_duplicate_number(to_number, request_id, replied_from):
    message = (
        f"ℹ️ *LocalFind Update*\n\n"
        f"Request #{request_id} ka reply already de diya gaya hai "
        f"({replied_from} number se).\n\n"
        f"Aapko kuch karna nahi hai. ✅"
    )
    send_whatsapp(to_number, message)


def notify_user(user_phone, shop_name, item_name, price, distance_km, request_id):
    message = (
        f"🏪 *{shop_name}* has responded!\n\n"
        f"*Item:* {item_name}\n"
        f"*Price:* ₹{int(price)}\n"
        f"*Distance:* {distance_km} km away\n\n"
        f"Visit http://localhost:5000/search to see all responses! 🛒"
    )
    send_whatsapp(user_phone, message)


def handle_incoming_message(from_number, body):
    from db.schema import get_db
    print("🔴 HANDLE CALLED!")
    
    phone = from_number.replace('whatsapp:+', '').replace('whatsapp: ', '').replace('+', '').strip()
    print(f"🔍 Phone: '{phone}'")

    body = body.strip().upper()
    parts = body.split()

    db = get_db()
    try:
        shop = db.execute(
            "SELECT * FROM shops WHERE wa_primary=? AND is_active=1",
            (phone,)
        ).fetchone()

        if not shop:
            shop = db.execute(
                "SELECT * FROM shops WHERE wa_backup=? AND is_active=1",
                (phone,)
            ).fetchone()

        print(f"🏪 Shop found: {shop is not None}")

        if not shop:
            return "Sorry, your number is not registered on LocalFind. Please register at http://localhost:5000"

        if len(parts) >= 2 and parts[0] == 'YES':
            request_id = int(parts[1])
            replied_from = 'primary' if phone == shop['wa_primary'] else 'backup'

            existing = db.execute(
                "SELECT * FROM responses WHERE request_id=? AND shop_id=? AND status='available'",
                (request_id, shop['id'])
            ).fetchone()

            if existing and existing['replied_from'] != replied_from:
                notify_duplicate_number(phone, request_id, existing['replied_from'])
                return f"Request #{request_id} was already replied by your {existing['replied_from']} number."

            db.execute("""
                UPDATE responses
                SET status='available', replied_from=?, wa_number=?, replied_at=datetime('now')
                WHERE request_id=? AND shop_id=?
            """, (replied_from, phone, request_id, shop['id']))
            db.commit()

            other_number = shop['wa_backup'] if replied_from == 'primary' else shop['wa_primary']
            if other_number:
                notify_duplicate_number(other_number, request_id, replied_from)

            return f"✅ Great! Marked as available for Request #{request_id}. Now send price:\nPRICE {request_id} <amount>"

        elif len(parts) >= 2 and parts[0] == 'NO':
            request_id = int(parts[1])
            db.execute("""
                UPDATE responses
                SET status='unavailable', replied_at=datetime('now')
                WHERE request_id=? AND shop_id=?
            """, (request_id, shop['id']))
            db.commit()
            return f"❌ Marked as unavailable for Request #{request_id}."

        elif len(parts) >= 3 and parts[0] == 'PRICE':
            request_id = int(parts[1])
            price = float(parts[2])

            db.execute(
                "UPDATE responses SET price=? WHERE request_id=? AND shop_id=?",
                (price, request_id, shop['id'])
            )
            db.commit()

            req = db.execute('SELECT * FROM requests WHERE id=?', (request_id,)).fetchone()
            if req:
                notify_user(req['user_phone'], shop['shop_name'],
                            req['item_name'], price, 0, request_id)

            return f"💰 Price ₹{int(price)} set for Request #{request_id}. User has been notified!"

        else:
            return (
                "Commands:\n"
                "✅ YES <id> — item available\n"
                "❌ NO <id> — not available\n"
                "💰 PRICE <id> <amount> — set price"
            )

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return f"Error: {str(e)}"
    finally:
        db.close()