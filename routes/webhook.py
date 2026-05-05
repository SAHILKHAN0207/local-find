from flask import Blueprint, request, Response
from bot import handle_incoming_message

webhook_bp = Blueprint('webhook', __name__, url_prefix='/webhook')

@webhook_bp.route('/whatsapp', methods=['POST'])
def whatsapp_webhook():
    from_number = request.form.get('From', '')
    body = request.form.get('Body', '')

    print(f"📩 Message from {from_number}: {body}", flush=True)

    reply = handle_incoming_message(from_number, body)

    print(f"📤 Reply: {reply}", flush=True)

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{reply}</Message>
</Response>"""

    return Response(twiml, mimetype='text/xml')