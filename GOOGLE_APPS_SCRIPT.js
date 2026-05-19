/**
 * Go Tím CRM Logger — Google Apps Script
 * ========================================
 * Nhận POST từ Railway bot, ghi vào Google Sheet.
 *
 * CÁCH SETUP (làm 1 lần duy nhất, ~5 phút):
 * 1. Mở Google Sheet mới: https://sheets.google.com → tạo sheet, đặt tên "Go Tím CRM"
 * 2. Vào menu: Extensions → Apps Script
 * 3. Xóa hết code cũ → Paste toàn bộ file này vào
 * 4. Click Deploy → New deployment → chọn type: Web app
 *    - Execute as: Me (your Google account)
 *    - Who has access: Anyone
 * 5. Click Deploy → Copy Web app URL
 * 6. Vào Railway dashboard → Variables → thêm:
 *    GSHEET_WEBHOOK_URL = [URL vừa copy]
 * 7. Redeploy Railway (hoặc tự động deploy khi save env vars)
 *
 * XONG! Mỗi tin nhắn bot xử lý sẽ tự ghi vào Sheet.
 */

function doPost(e) {
  try {
    var data = JSON.parse(e.postData.contents);
    var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();

    // Tạo header nếu sheet mới (row 1 trống)
    if (sheet.getLastRow() === 0) {
      sheet.appendRow(['Thời gian', 'Sender ID', 'Tin nhắn khách', 'Bot trả lời']);
      sheet.getRange(1, 1, 1, 4).setFontWeight('bold');
    }

    sheet.appendRow([
      data.timestamp || new Date().toLocaleString('vi-VN'),
      data.sender_id  || '',
      data.message    || '',
      data.reply      || ''
    ]);

    return ContentService
      .createTextOutput(JSON.stringify({ status: 'ok', rows: sheet.getLastRow() }))
      .setMimeType(ContentService.MimeType.JSON);

  } catch (err) {
    return ContentService
      .createTextOutput(JSON.stringify({ status: 'error', msg: err.toString() }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

// Test thủ công: chạy hàm này để kiểm tra sheet hoạt động
function testLog() {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  sheet.appendRow(['2026-05-19 TEST', '123456789', 'Xin chào', 'Dạ chào Anh/Chị! 💜']);
  Logger.log('Test row added at row ' + sheet.getLastRow());
}
