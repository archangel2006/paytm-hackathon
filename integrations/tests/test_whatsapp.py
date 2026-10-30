import hashlib
import hmac

from integrations.whatsapp import parser
from integrations.whatsapp.security import verify_signature


def test_signature_validation():
    body = b'{"ok":true}'
    secret = "secret"
    signature = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_signature(body, signature, secret)
    assert not verify_signature(body + b"!", signature, secret)


def test_parser_extracts_text_media_and_status():
    events = parser.parse_payload({
        "entry": [{"changes": [{"value": {
            "messages": [
                {"id": "t1", "from": "919876543210", "timestamp": "1700000000", "type": "text", "text": {"body": "hi"}},
                {"id": "i1", "from": "919876543210", "timestamp": "1700000001", "type": "image", "image": {"id": "media1", "mime_type": "image/jpeg"}},
            ],
            "statuses": [{"id": "t1", "status": "delivered"}],
        }}]}]
    })
    assert [event.kind for event in events] == ["status", "text", "media"]
    assert events[1].text == "hi"
    assert events[0].raw["status"] == "delivered"
