# Go Tím AI Chatbot Server — Em Linh 🛵

Bot tự động trả lời tin nhắn Facebook Messenger bằng Gemini AI.  
Deploy 24/7 trên Railway.app, direct webhook — không qua Make.com.

## 🏗️ Kiến trúc

```
Khách nhắn Fanpage "Go Tím Za-lo"
    ↓
Facebook App Webhook (direct)
    ↓
Railway: POST /webhook → Gemini AI (OpenRouter)
    ↓
FB Graph API gửi reply trực tiếp
    ↓
[Song song] Telegram notification (nếu booking intent)
[Song song] Google Sheets CRM logging (via Apps Script)
```

## 🔑 Environment Variables (Railway)

| Key | Mô tả |
|-----|-------|
| `FB_PAGE_TOKEN` | Permanent page token (never expires) |
| `FB_PAGE_ID` | `1140598805792501` |
| `OPENROUTER_API_KEY` | AI model key |
| `WEBHOOK_VERIFY_TOKEN` | `gotim_secret_2026` |
| `TELEGRAM_BOT_TOKEN` | Bot token để ping admin khi có đặt xe |
| `TELEGRAM_CHAT_ID` | Chat ID của admin |
| `GSHEET_WEBHOOK_URL` | Apps Script URL để log CRM vào Sheets |

## 📡 API Endpoints

| Method | Path | Mô tả |
|--------|------|-------|
| GET | `/` | Health check |
| GET/POST | `/webhook` | Facebook direct webhook |
| POST | `/make-webhook` | Legacy Make.com (vẫn giữ, không dùng) |
| GET | `/stats` | Xem thống kê conversations |

## ✅ Tính năng

- **AI Em Linh**: trả lời tự nhiên, đúng giá dịch vụ Go Tím
- **Conversation memory**: nhớ 10 tin gần nhất mỗi user
- **Booking notification**: khi khách nhắn "đặt xe / ship / giao", admin nhận Telegram ngay
- **CRM logging**: mọi cuộc trò chuyện ghi vào Google Sheets tự động
- **Fallback**: nếu AI fail → trả lời mặc định kèm hotline

## 🧪 Test local

```bash
pip install -r requirements.txt
FB_PAGE_TOKEN=xxx OPENROUTER_API_KEY=xxx python app.py

# Test booking notification
curl -X POST http://localhost:5678/make-webhook \
  -H "Content-Type: application/json" \
  -d '{"sender_id":"test123","message":"em muốn đặt xe đi chợ","sender_name":"Khách"}'
```
