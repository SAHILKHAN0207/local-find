"""
LocalFind — WhatsApp Bot
Handles incoming WhatsApp messages from shop owners
and sends notifications to shops when user makes a request
"""

import os
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()

ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
AUTH_TOKEN  = os.getenv('TWILIO_AUTH_TOKEN')
FROM_NUMBER = os.getenv('TWILIO_WHATSAPP_NUMBER')

client = Client(ACCOUNT_SID, AUTH_TOKEN)


def send_whatsapp(to_number: str, message: str):
    """
    Send a WhatsApp message to a number.
    to_number format: '919876543210' (no + sign)
    """
    try:
        msg = client.messages.create(
            from_=FROM_NUMBER,
            to=f'whatsapp:+{to_number}',
            body=message
        )
        print(f"✅ Message sent to +{to_number} — SID: {msg.sid}")
        return True
    except Exception as e:
        print(f"❌ Failed to send to +{to_number} — {str(e)}")
        return False


def notify_shop(shop, request_id: int, item_name: str, distance_km: float):
    """
    Send request notification to a shop.
    Sends to both primary and backup number if available.
    """
    message = (
        f"🔔 *New LocalFind Request!*\n\n"
        f"*Item:* {item_name}\n"
        f"*Request ID:* #{request_id}\n"
        f"*Distance:* {distance_km} km from your shop\n\n"
        f"Reply with:\n"
        f"✅ *YES {request_id}* — if available\n"
        f"❌ *NO {request_id}* — if not available\n\n"
        f"To set price reply:\n"
        f"💰 *PRICE {request_id} 25000*"
    )

    # Send to primary number
    send_whatsapp(shop['wa_primary'], message)

    # Send to backup number if exists
    if shop.get('wa_backup'):
        send_whatsapp(shop['wa_backup'], message)


def notify_duplicate_number(to_number: str, request_id: int, replied_from: str):
    """
    When one number already replied, notify the other number.
    """
    message = (
        f"ℹ️ *LocalFind Update*\n\n"
        f"Request #{request_id} ka reply already de diya gaya hai "
        f"({replied_from} number se).\n\n"
        f"Aapko kuch karna nahi hai. ✅"
    )
    send_whatsapp(to_number, message)


def notify_user(user_phone: str, shop_name: str, item_name: str,
                price: float, distance_km: float, request_id: int):
    """
    Notify user when a shop responds with availability and price.
    """
    message = (
        f"🏪 *{shop_name}* has responded!\n\n"
        f"*Item:* {item_name}\n"
        f"*Price:* ₹{int(price)}\n"
        f"*Distance:* {distance_km} km away\n\n"
        f"Visit http://localhost:5000/search to see all responses\n"
        f"and place your order on WhatsApp! 🛒"
    )
    send_whatsapp(user_phone, message)


def handle_incoming_message(from_number: str, body: str):
    """
    Process incoming WhatsApp replies from shop owners.
    
    Supported commands:
    YES <request_id>               — mark as available
    NO <request_id>                — mark as unavailable  
    PRICE <request_id> <amount>    — set price
    """
    from db.schema import get_db
    import json

    # Clean up number — remove 'whatsapp:+' prefix
    phone = from_number.replace('whatsapp:+', '').replace('+', '')

    body = body.strip().upper()
    parts = body.split()

    db = get_db()
    try:
        # Find shop by primary or backup number
        shop = db.execute("""
            SELECT * FROM shops
            WHERE wa_primary=? OR wa_backup=?
              AND is_active=1
        """, (phone, phone)).fetchone()

        if not shop:
            return "Sorry, your number is not registered on LocalFind. Please register at http://localhost:5000"

        # ── YES <request_id> ──────────────────────────────────────────────
        if len(parts) >= 2 and parts[0] == 'YES':
            request_id = int(parts[1])
            replied_from = 'primary' if phone == shop['wa_primary'] else 'backup'

            # Check if other number already replied
            existing = db.execute("""
                SELECT * FROM responses
                WHERE request_id=? AND shop_id=?
                  AND status='available'
            """, (request_id, shop['id'])).fetchone()

            if existing and existing['replied_from'] != replied_from:
                # Other number already replied — send lock message
                notify_duplicate_number(phone, request_id, existing['replied_from'])
                return f"Request #{request_id} was already replied by your {existing['replied_from']} number."

            # Save response
            db.execute("""
                UPDATE responses
                SET status='available', replied_from=?, wa_number=?, replied_at=datetime('now')
                WHERE request_id=? AND shop_id=?
            """, (replied_from, phone, request_id, shop['id']))
            db.commit()

            # If other WA number exists, notify it
            other_number = shop['wa_backup'] if replied_from == 'primary' else shop['wa_primary']
            if other_number:
                notify_duplicate_number(other_number, request_id, replied_from)

            return f"✅ Great! Marked as available for Request #{request_id}. Now send price:\nPRICE {request_id} <amount>"

        # ── NO <request_id> ───────────────────────────────────────────────
        elif len(parts) >= 2 and parts[0] == 'NO':
            request_id = int(parts[1])
            db.execute("""
                UPDATE responses
                SET status='unavailable', replied_at=datetime('now')
                WHERE request_id=? AND shop_id=?
            """, (request_id, shop['id']))
            db.commit()
            return f"❌ Marked as unavailable for Request #{request_id}."

        # ── PRICE <request_id> <amount> ───────────────────────────────────
        elif len(parts) >= 3 and parts[0] == 'PRICE':
            request_id = int(parts[1])
            price = float(parts[2])

            db.execute("""
                UPDATE responses SET price=?
                WHERE request_id=? AND shop_id=?
            """, (price, request_id, shop['id']))
            db.commit()

            # Notify user about this shop's response
            req = db.execute('SELECT * FROM requests WHERE id=?', (request_id,)).fetchone()
            if req:
                notify_user(
                    req['user_phone'], shop['shop_name'],
                    req['item_name'], price, 0, request_id
                )

            return f"💰 Price ₹{int(price)} set for Request #{request_id}. User has been notified!"

        else:
            return (
                "Commands:\n"
                "✅ YES <id> — item available\n"
                "❌ NO <id> — not available\n"
                "💰 PRICE <id> <amount> — set price"
            )

    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        db.close()