"""
app.py — Go Tím AI Chatbot Server
===================================
Flask webhook server nhận tin nhắn từ Make.com,
xử lý qua Gemini AI, trả kết quả về Make.com để gửi reply.

Deploy: Railway.app (free, 24/7, không sleep)
Local:  python app.py
"""

import os
import json
import logging
from datetime import datetime
from threading import Thread
from flask import Flask, request, jsonify
import requests

# ─── FLASK APP ───
app = Flask(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
log = logging.getLogger('GoTimBot')

# ─── CREDENTIALS (đọc từ env vars — set trong Railway dashboard) ───
PAGE_ACCESS_TOKEN  = os.environ.get('FB_PAGE_TOKEN', '')
PAGE_ID            = os.environ.get('FB_PAGE_ID', '1140598805792501')
OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY', '')
VERIFY_TOKEN       = os.environ.get('WEBHOOK_VERIFY_TOKEN', 'gotim_secret_2026')
GSHEET_WEBHOOK_URL = os.environ.get('GSHEET_WEBHOOK_URL', '')  # Google Apps Script URL

# ─── SERVICE INFO ───
HOTLINE     = '0943 50 50 77'
ZALO_NUMBER = '0334 759 394'
LANDING_URL = 'https://gotimlanding.vercel.app'

# ─── SYSTEM PROMPT ─── (não của chatbot)
SYSTEM_PROMPT = """Bạn là "Go Tím Bot" — Trợ lý ảo chăm sóc khách hàng của dịch vụ xe ôm công nghệ Go Tím tại Bạc Liêu.

THÔNG TIN DỊCH VỤ:
- Dịch vụ: Xe ôm, Giao hàng, Mua hộ
- Khu vực: Phước Long, Bạc Liêu, Cà Mau
- Bảng giá Xe Ôm: 18.000đ/2km đầu, 5.000đ/km tiếp theo
- Bảng giá Ship/Mua hộ: 15.000đ/2km đầu, 4.000đ/km tiếp theo
- Không phụ phí ban đêm
- Zalo đặt xe: 0334 759 394
- Hotline: 0943 50 50 77
- Website: https://gotimlanding.vercel.app

QUY TẮC TRẢ LỜI:
1. Trả lời NGẮN GỌN (tối đa 3-4 câu), thân thiện, dùng emoji vừa phải.
2. LUÔN hướng khách hàng đến HÀNH ĐỘNG cụ thể (đặt xe, gọi hotline, nhắn Zalo).
3. Nếu khách hỏi giá → báo giá rõ ràng + hỏi "Anh/Chị cần đặt xe luôn không?".
4. Nếu khách muốn đặt xe → xin: Điểm đón + Điểm đến + SĐT.
5. Nếu khách muốn đăng ký tài xế → xin: Họ tên + SĐT + Loại xe.
6. Xưng "em", gọi khách "Anh/Chị".
7. Kết thúc bằng CTA rõ ràng.
8. KHÔNG bịa thông tin. Nếu không biết → hướng dẫn gọi hotline.

KỊCH BẢN ƯU TIÊN:
- "GO" hoặc đăng ký tài xế → Thu thập: Họ tên + SĐT + Loại xe
- "ĐẶT/DAT" hoặc đặt xe → Thu thập: Điểm đón + Điểm đến + SĐT
- "SHIP/GIAO" → Phân loại giao hàng/mua hộ → Thu thập thông tin
- Hỏi giá → Báo bảng giá + CTA đặt xe
- Chào hỏi → Chào lại + giới thiệu ngắn + hỏi nhu cầu"""

# ─── CRM LOGGING → GOOGLE SHEETS (via Apps Script webhook, no OAuth) ───
def log_crm(sender_id: str, sender_name: str, message: str, reply: str):
    if not GSHEET_WEBHOOK_URL:
        return
    def _post():
        try:
            requests.post(GSHEET_WEBHOOK_URL, json={
                "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "sender_id": sender_id,
                "sender_name": sender_name,
                "message": message,
                "reply": reply
            }, timeout=5)
        except Exception:
            pass  # non-blocking, never crash bot
    Thread(target=_post, daemon=True).start()


# ─── IN-MEMORY CONVERSATION (Railway không có persistent disk) ───
# Lưu lịch sử tối đa 50 users, mỗi user tối đa 10 messages
_conversations: dict = {}

def get_history(sender_id: str) -> list:
    return _conversations.get(sender_id, {}).get('messages', [])

def save_message(sender_id: str, role: str, content: str):
    if sender_id not in _conversations:
        _conversations[sender_id] = {'messages': [], 'first_seen': datetime.now().isoformat()}
    _conversations[sender_id]['messages'].append({'role': role, 'content': content})
    _conversations[sender_id]['messages'] = _conversations[sender_id]['messages'][-10:]
    _conversations[sender_id]['last_active'] = datetime.now().isoformat()
    # Giới hạn 50 users (free tier memory)
    if len(_conversations) > 50:
        oldest = min(_conversations, key=lambda k: _conversations[k].get('last_active', ''))
        del _conversations[oldest]


# ─── GEMINI AI VIA OPENROUTER ───
def ask_ai(sender_id: str, user_message: str) -> str | None:
    history = get_history(sender_id)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in history[-6:]:
        messages.append({"role": msg['role'], "content": msg['content']})
    messages.append({"role": "user", "content": user_message})

    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": LANDING_URL,
                "X-Title": "GoTim AI Bot"
            },
            json={
                "model": "google/gemini-2.5-flash",
                "messages": messages,
                "max_tokens": 300,
                "temperature": 0.7
            },
            timeout=20
        )
        data = resp.json()
        if 'choices' in data and data['choices']:
            reply = data['choices'][0]['message']['content'].strip()
            save_message(sender_id, 'user', user_message)
            save_message(sender_id, 'assistant', reply)
            log.info(f"✅ AI replied [{sender_id[:8]}]: {reply[:80]}")
            return reply
        log.error(f"AI error: {json.dumps(data)[:200]}")
        return None
    except Exception as e:
        log.error(f"AI request failed: {e}")
        return None


# ─── FACEBOOK SEND MESSAGE (trực tiếp qua Graph API) ───
def fb_send(recipient_id: str, text: str) -> bool:
    if not PAGE_ACCESS_TOKEN:
        log.warning("FB_PAGE_TOKEN chưa set!")
        return False
    try:
        resp = requests.post(
            f"https://graph.facebook.com/v19.0/me/messages",
            params={"access_token": PAGE_ACCESS_TOKEN},
            json={
                "recipient": {"id": recipient_id},
                "message": {"text": text},
                "messaging_type": "RESPONSE"
            },
            timeout=10
        )
        result = resp.json()
        if 'error' in result:
            log.error(f"FB send error: {result['error'].get('message')}")
            return False
        return True
    except Exception as e:
        log.error(f"FB send failed: {e}")
        return False


# ══════════════════════════════════════════
# ROUTES
# ══════════════════════════════════════════

@app.get("/")
def health():
    """Health check — Railway ping endpoint"""
    return jsonify({
        "status": "🟢 online",
        "service": "Go Tím AI Chatbot Server",
        "ai_model": "google/gemini-2.5-flash",
        "active_conversations": len(_conversations),
        "timestamp": datetime.now().isoformat()
    })


@app.get("/webhook")
def fb_verify():
    """Facebook Webhook Verification (dùng nếu kết nối FB App trực tiếp)"""
    mode  = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        log.info("✅ Facebook webhook verified!")
        return challenge, 200
    return "Forbidden", 403


@app.post("/webhook")
def fb_webhook():
    """Nhận events trực tiếp từ Facebook (bypass Make.com hoàn toàn)"""
    data = request.json or {}
    if data.get("object") != "page":
        return jsonify({"status": "ignored"}), 200

    for entry in data.get("entry", []):
        for event in entry.get("messaging", []):
            sender_id = event.get("sender", {}).get("id")
            msg = event.get("message", {})
            text = msg.get("text", "").strip()

            if not sender_id or not text or msg.get("is_echo"):
                continue

            log.info(f"📩 FB direct [{sender_id[:8]}]: {text[:60]}")
            reply = ask_ai(sender_id, text)
            if not reply:
                reply = f"Cảm ơn Anh/Chị! 💜 Để được hỗ trợ nhanh, vui lòng gọi Hotline: {HOTLINE} hoặc nhắn Zalo: {ZALO_NUMBER} ạ!"
            fb_send(sender_id, reply)
            log_crm(sender_id, sender_id, text, reply)

    return jsonify({"status": "ok"}), 200


@app.post("/make-webhook")
def make_webhook():
    """
    Nhận tin từ Make.com (kịch bản: Make.com gọi webhook này, server reply lại JSON)
    Make.com sau đó dùng {{response.reply}} để gửi tin nhắn FB.
    
    Body nhận vào:
      { "sender_id": "...", "message": "...", "sender_name": "..." }
    
    Body trả về:
      { "reply": "...", "sender_id": "..." }
    """
    data = request.json or {}
    sender_id   = data.get("sender_id", "")
    message     = data.get("message", "").strip()
    sender_name = data.get("sender_name", "Khách")

    if not sender_id or not message:
        return jsonify({"error": "Missing sender_id or message"}), 400

    log.info(f"📩 Make.com [{sender_id[:8]}] {sender_name}: {message[:60]}")

    reply = ask_ai(sender_id, message)
    if not reply:
        reply = f"Cảm ơn {sender_name}! 💜 Để được hỗ trợ nhanh, vui lòng gọi Hotline: {HOTLINE} ạ!"

    return jsonify({
        "reply": reply,
        "sender_id": sender_id,
        "sender_name": sender_name,
        "timestamp": datetime.now().isoformat()
    })


@app.get("/stats")
def stats():
    """Xem thống kê conversations"""
    return jsonify({
        "total_users": len(_conversations),
        "users": [
            {
                "id": uid[:8] + "...",
                "messages": len(v['messages']),
                "last_active": v.get('last_active', '')[:16]
            }
            for uid, v in list(_conversations.items())[-10:]
        ]
    })


# ─── LOCAL DEV ───
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5678))
    log.info(f"🛵 Go Tím AI Bot running on port {port}")
    log.info(f"   Health:       GET  http://localhost:{port}/")
    log.info(f"   Make.com:     POST http://localhost:{port}/make-webhook")
    log.info(f"   FB direct:    POST http://localhost:{port}/webhook")
    app.run(host="0.0.0.0", port=port, debug=False)
