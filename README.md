# Go Tím AI Chatbot Server

Bot tự động trả lời tin nhắn Facebook Messenger bằng Gemini AI.
Deploy 24/7 trên Railway.app (free tier, không sleep).

## 🏗️ Kiến trúc

```
Khách nhắn Fanpage "Go Tím Za-lo"
    ↓
[Tùy chọn A] Make.com → POST /make-webhook → Gemini AI → JSON reply → Make.com gửi FB
[Tùy chọn B] Facebook App Webhook → POST /webhook → Gemini AI → FB Graph API gửi trực tiếp
```

## 🚀 Deploy lên Railway (5 phút)

### Bước 1: Push lên GitHub
```bash
git init
git add .
git commit -m "Go Tim AI Chatbot Server"
git remote add origin https://github.com/YOUR_USERNAME/gotim-chatbot
git push -u origin main
```

### Bước 2: Deploy Railway
1. Vào https://railway.app → Login bằng GitHub
2. **New Project** → **Deploy from GitHub repo**
3. Chọn repo `gotim-chatbot`
4. Railway tự detect Python và build

### Bước 3: Set Environment Variables
Trong Railway dashboard → Variables → Add:

| Key | Value |
|-----|-------|
| `FB_PAGE_TOKEN` | (Page Access Token từ token_result.json) |
| `FB_PAGE_ID` | `1140598805792501` |
| `OPENROUTER_API_KEY` | `sk-or-v1-8eadce4c...` |
| `WEBHOOK_VERIFY_TOKEN` | `gotim_secret_2026` |

### Bước 4: Lấy URL và cấu hình Make.com
Railway sẽ cho URL dạng: `https://gotim-chatbot-production.up.railway.app`

Vào Make.com → Scenario "Integration Facebook Messenger, HTTP":
- Module HTTP → URL: `https://gotim-chatbot-production.up.railway.app/make-webhook`
- Method: POST
- Body:
```json
{
  "sender_id": "{{1.senderId}}",
  "message": "{{1.message}}",
  "sender_name": "{{1.senderName}}"
}
```
- Module cuối FB Send → Message: `{{2.data.reply}}`

## 📡 API Endpoints

| Method | Path | Mô tả |
|--------|------|-------|
| GET | `/` | Health check |
| POST | `/make-webhook` | Nhận từ Make.com, trả JSON reply |
| GET/POST | `/webhook` | Facebook App Webhook trực tiếp |
| GET | `/stats` | Xem thống kê conversations |

## 🧪 Test local
```bash
pip install -r requirements.txt
FB_PAGE_TOKEN=xxx OPENROUTER_API_KEY=xxx python app.py

# Test webhook
curl -X POST http://localhost:5678/make-webhook \
  -H "Content-Type: application/json" \
  -d '{"sender_id":"test123","message":"xin chào","sender_name":"Khách test"}'
```
