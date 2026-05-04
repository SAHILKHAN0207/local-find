"""
LocalFind — WhatsApp Webhook
Twilio sends incoming WhatsApp messages here
"""

from flask import Blueprint, request, Response
from bot import handle_incoming_message

webhook_bp = Blueprint('webhook', __name__, url_prefix='/webhook')


@webhook_bp.route('/whatsapp', methods=['POST'])
def whatsapp_webhook():
    """
    Twilio sends incoming WhatsApp messages to this endpoint.
    Shop owner replies (YES/NO/PRICE) are handled here.
    """
    from_number = request.form.get('From', '')
    body        = request.form.get('Body', '')

    print(f"📩 Message from {from_number}: {body}")

    reply = handle_incoming_message(from_number, body)

    # Twilio expects TwiML response
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{reply}</Message>
</Response>"""

    return Response(twiml, mimetype='text/xml')