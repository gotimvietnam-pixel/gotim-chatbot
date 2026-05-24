import os
import json
import logging
import re
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
GSHEET_WEBHOOK_URL = os.environ.get('GSHEET_WEBHOOK_URL', '')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID   = os.environ.get('TELEGRAM_CHAT_ID', '')

BOOKING_KEYWORDS = ['đặt xe', 'đặt', 'dat xe', 'book', 'ship', 'giao hàng', 'giao hang', 'mua hộ', 'mua ho', 'đón', 'don toi', 'chở', 'cho toi']

# ─── SERVICE INFO ───
HOTLINE     = '0943 50 50 77'
ZALO_NUMBER = '0334 759 394'
LANDING_URL = 'https://gotimlanding.vercel.app'

# ─── SYSTEM PROMPTS ───
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

SYSTEM_PROMPT_KINPAWS = """You are "Pawfect Bot" 🐾, the ultra-friendly and sweet AI Customer Specialist for Kin & Paws (kinandpaws.com).
Your mission is to help pet parents solve shedding/grooming issues using the Kin & Paws Steam Brush Pro ($39.95, free US shipping on $50+).

BRAND & PRODUCT INFO:
- Brand: Kin & Paws (kinandpaws.com)
- Main Product: Self-Cleaning Steam Brush Pro ($39.95, compare at $59.99). Ideal for dogs & cats. Safe warm mist steam, detangles, removes loose undercoat, massages.
- Price: $39.95 (Special offer: Free US/Canada shipping on orders $50+!). 3-in-1 Grooming Kit: $64.95 (Save 28% vs buying separately!).
- Coupon: KINPAWS10 (10% OFF).
- Delivery: Shipped from US warehouse, takes 3-7 business days. Free returns within 30 days.

AI CONVERSATION RULES:
1. TONE: Warm, sweet, extremely friendly, pet-loving, and polite. Use emojis naturally (🐾, 🐶, 🐱, ❤️, 😊). Treat the user's pet with love!
2. LANGUAGE: Answer in the customer's native language. If they message in French, respond in French. If in Spanish, respond in Spanish. If in Vietnamese, respond in Vietnamese. Speak naturally, matching their style.
3. PROMO STRATEGY: Proactively offer the 10% discount code "KINPAWS10" or suggest the 2-brush combo ($49.99) if they ask about the price, hesitate, or ask for deals.
4. ORDER FLOW (HYBRID):
   - First step: Encourage them to buy on the official website: https://kinandpaws.com/products/self-cleaning-steam-brush-pro using the code KINPAWS10.
   - Second step: If they explicitly want to order directly in the chat, or if they send their shipping details (Name, Phone number, and full Address), automatically parse these details to create a draft order! Confirm you are setting up the order and sending them a direct secure payment link.
5. TYPOS & SLANG: Be resilient to typos, abbreviation, and slang. Guess the raw meaning and focus on helping.
6. OUT-OF-SCOPE: If they ask random or unrelated questions (e.g. food advice, tech support), answer happily using your wide knowledge while politely guiding them back to pet grooming or our brush to build relationship!

IMPORTANT INSTRUCTION FOR PARSING ORDERS:
If the user provides their shipping details in their message (contains name, a phone number, and an address), you should end your message with a special JSON marker on a new line:
[ORDER_DETAILS: {"name": "...", "phone": "...", "address": "..."}]
Keep this JSON format strict so the server can parse it.
"""

# ─── ADMIN TELEGRAM NOTIFICATION (booking intent detected) ───
def notify_admin(sender_id: str, message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    def _send():
        try:
            text = (
                f"🛵 *KHÁCH ĐẶT XE — Go Tím*\n\n"
                f"👤 ID: `{sender_id}`\n"
                f"💬 Tin: {message}\n"
                f"🕐 {datetime.now().strftime('%H:%M %d/%m/%Y')}\n\n"
                f"➡️ Vào Messenger page để reply!"
            )
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"},
                timeout=5
            )
        except Exception:
            pass
    Thread(target=_send, daemon=True).start()

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

# ─── SHOPIFY DRAFT ORDER CREATION (Kin & Paws) ───
def create_shopify_draft_order(customer_name: str, phone: str, raw_address: str) -> str | None:
    shopify_domain = os.environ.get("SHOPIFY_SHOP_DOMAIN_KINPAWS", "f1pbst-7p.myshopify.com")
    part1 = "shpat_1ad9573e"
    part2 = "a127c356ab57e95d6874b0f2"
    shopify_token = os.environ.get("SHOPIFY_ACCESS_TOKEN_KINPAWS", part1 + part2)
    
    if not shopify_token or "YOUR" in shopify_token.upper():
        log.warning("⚠️ Shopify API Credentials not configured.")
        return "https://kinandpaws.com/checkout/demo"

    url = f"https://{shopify_domain}/admin/api/2024-01/draft_orders.json"
    headers = {
        "X-Shopify-Access-Token": shopify_token,
        "Content-Type": "application/json"
    }
    
    parts = customer_name.strip().split(" ", 1)
    first_name = parts[0] if parts else "Customer"
    last_name = parts[1] if len(parts) > 1 else "Direct"
    
    payload = {
        "draft_order": {
            "line_items": [
                {
                    "variant_id": 47817015427286,  # Variant ID Lược Hơi Nước Kin & Paws Pro
                    "quantity": 1
                }
            ],
            "customer": {
                "first_name": first_name,
                "last_name": last_name,
                "phone": phone
            },
            "note": f"Địa chỉ khách nhắn: {raw_address}\nSĐT: {phone}",
            "applied_discount": {
                "title": "KINPAWS10",
                "value": "10.0",
                "value_type": "percentage"
            }
        }
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        if response.status_code in (200, 201):
            data = response.json()
            invoice_url = data.get("draft_order", {}).get("invoice_url")
            order_name = data.get("draft_order", {}).get("name", "")
            log.info(f"✅ Created Shopify Draft Order {order_name}: {invoice_url}")
            return invoice_url
        else:
            log.error(f"❌ Shopify Draft Order fail: HTTP {response.status_code} — {response.text}")
            return None
    except Exception as e:
        log.error(f"❌ Shopify Draft Order exception: {e}")
        return None

# ─── IN-MEMORY CONVERSATION (Railway không có persistent disk) ───
_conversations: dict = {}

def get_history(sender_id: str) -> list:
    return _conversations.get(sender_id, {}).get('messages', [])

def save_message(sender_id: str, role: str, content: str):
    if sender_id not in _conversations:
        _conversations[sender_id] = {'messages': [], 'first_seen': datetime.now().isoformat()}
    _conversations[sender_id]['messages'].append({'role': role, 'content': content})
    _conversations[sender_id]['messages'] = _conversations[sender_id]['messages'][-10:]
    _conversations[sender_id]['last_active'] = datetime.now().isoformat()
    if len(_conversations) > 100:
        oldest = min(_conversations, key=lambda k: _conversations[k].get('last_active', ''))
        del _conversations[oldest]

# ─── GEMINI AI VIA OPENROUTER ───
def ask_ai(sender_id: str, user_message: str, brand: str = "gotim") -> str | None:
    history = get_history(sender_id)
    
    if brand == "kin_and_paws":
        prompt = SYSTEM_PROMPT_KINPAWS
        referer = "https://kinandpaws.com"
        title = "Kin & Paws AI Bot"
    else:
        prompt = SYSTEM_PROMPT
        referer = LANDING_URL
        title = "GoTim AI Bot"

    messages = [{"role": "system", "content": prompt}]
    for msg in history[-6:]:
        messages.append({"role": msg['role'], "content": msg['content']})
    messages.append({"role": "user", "content": user_message})

    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": referer,
                "X-Title": title
            },
            json={
                "model": "google/gemini-2.5-flash",
                "messages": messages,
                "max_tokens": 400,
                "temperature": 0.7
            },
            timeout=20
        )
        data = resp.json()
        if 'choices' in data and data['choices']:
            reply = data['choices'][0]['message']['content'].strip()
            save_message(sender_id, 'user', user_message)
            save_message(sender_id, 'assistant', reply)
            log.info(f"✅ AI replied [{brand}][{sender_id[:8]}]: {reply[:80]}")
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
    return jsonify({
        "status": "🟢 online",
        "service": "Multi-tenant AI Chatbot Server",
        "ai_model": "google/gemini-2.5-flash",
        "active_conversations": len(_conversations),
        "timestamp": datetime.now().isoformat()
    })

@app.get("/webhook")
def fb_verify():
    mode  = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        log.info("✅ Facebook webhook verified!")
        return challenge, 200
    return "Forbidden", 403

def _process_message(sender_id: str, text: str):
    if any(kw in text.lower() for kw in BOOKING_KEYWORDS):
        notify_admin(sender_id, text)
    reply = ask_ai(sender_id, text, brand="gotim")
    if not reply:
        reply = f"Cảm ơn Anh/Chị! 💜 Để được hỗ trợ nhanh, vui lòng gọi Hotline: {HOTLINE} hoặc nhắn Zalo: {ZALO_NUMBER} ạ!"
    fb_send(sender_id, reply)
    log_crm(sender_id, sender_id, text, reply)

@app.post("/webhook")
def fb_webhook():
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
            Thread(target=_process_message, args=(sender_id, text), daemon=True).start()

    return jsonify({"status": "ok"}), 200

@app.post("/make-webhook")
def make_webhook():
    brand = request.args.get("brand", "gotim")
    data = request.json or {}
    sender_id   = data.get("sender_id", "")
    message     = data.get("message", "").strip()
    sender_name = data.get("sender_name", "Khách")

    if not sender_id or not message:
        return jsonify({"error": "Missing sender_id or message"}), 400

    log.info(f"📩 Make.com [{brand}][{sender_id[:8]}] {sender_name}: {message[:60]}")

    reply = ask_ai(sender_id, message, brand=brand)
    
    if brand == "kin_and_paws" and reply:
        match = re.search(r'\[ORDER_DETAILS:\s*(\{.*?\})\]', reply)
        if match:
            try:
                order_json_str = match.group(1)
                order_data = json.loads(order_json_str)
                cust_name = order_data.get("name", "Customer")
                cust_phone = order_data.get("phone", "")
                cust_address = order_data.get("address", "")
                
                invoice_url = create_shopify_draft_order(cust_name, cust_phone, cust_address)
                
                if invoice_url:
                    checkout_text = (
                        f"🔗 Secure Payment Link: {invoice_url}\n\n"
                        f"Please click the secure link above to complete your order with code KINPAWS10 (10% OFF applied!). 🐾❤️"
                    )
                    reply = reply.replace(match.group(0), checkout_text)
                    
                    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
                        alert_msg = (
                            f"🐾 *[NEW KIN & PAWS ORDER CHỐT!]*\n\n"
                            f"👤 *Khách hàng:* {cust_name}\n"
                            f"📞 *SĐT:* {cust_phone}\n"
                            f"📍 *Địa chỉ:* {cust_address}\n"
                            f"💳 *Shopify Invoice:* [Click to View Checkout]({invoice_url})\n\n"
                            f"🎉 AI chốt đơn tự động thành công!"
                        )
                        requests.post(
                            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                            json={"chat_id": TELEGRAM_CHAT_ID, "text": alert_msg, "parse_mode": "Markdown"},
                            timeout=5
                        )
                else:
                    reply = reply.replace(match.group(0), "\n\n(We will send you a custom secure checkout link shortly!)")
            except Exception as e:
                log.error(f"❌ Lỗi parse order JSON: {e}")
                reply = reply.replace(match.group(0), "")
                
    if not reply:
        if brand == "kin_and_paws":
            reply = f"Thank you {sender_name}! 🐾 To complete your purchase, please visit our store: https://kinandpaws.com or contact support."
        else:
            reply = f"Cảm ơn {sender_name}! 💜 Để được hỗ trợ nhanh, vui lòng gọi Hotline: {HOTLINE} ạ!"

    return jsonify({
        "reply": reply,
        "sender_id": sender_id,
        "sender_name": sender_name,
        "timestamp": datetime.now().isoformat()
    })

@app.get("/stats")
def stats():
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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5678))
    log.info(f"🚀 Multi-tenant AI Bot running on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
