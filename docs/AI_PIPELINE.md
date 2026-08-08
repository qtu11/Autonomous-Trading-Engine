# QuantAI - AI Pipeline & Multi-AI Decision Engine

## Tổng Quan

QuantAI sử dụng pipeline quyết định nhiều lớp, kết hợp **hội tụ kỹ thuật tất định (deterministic technical confluence)**, **định cỡ rủi ro định lượng** và **phân tích cảm xúc nền tảng (fundamental AI sentiment)**. Kiến trúc quan trọng: model AI không tự quyết mở lệnh - nó chỉ bổ sung điểm cảm xúc/khuyến nghị phòng thủ; lệnh chỉ được tạo khi vượt qua RiskGate.

## Chuỗi Failover Multi-AI (Multi-AI Router / Auto Token Failover)

Khi cần gọi LLM, `server.py -> call_multi_ai_completion` chọn provider theo thứ tự ưu tiên:

```text
1. Custom Gateway (GATEWAY_URL + GATEWAY_KEY)      # Ưu tiên cao nhất - khách hàng tự cấu hình
2. Customer Custom Model ID (custom_model_id)      # Khách hàng chọn model cụ thể
3. OpenCode Zen Free Pool (Mặc định - không cần API Key)   <-- DEFAULT ACTIVE
   - deepseek-v4-flash-free (default) / big-pickle / mimo-v2.5-free
      / nemotron-3-ultra-free / north-mini-code-free / laguna-s-2.1-free / longcat-2.0-free
   - Final endpoint: https://opencode.ai/zen/v1/chat/completions
   - Tự XOAY VÒNG mỗi lượt; model lỗi 429/400/401 -> cooldown 300s rồi auto-switch
   - Lưu ý: OpenCode chặn User-Agent Python-urllib -> request phải gửi UA trình duyệt
4. Gemini Rotation Pool (xoay vòng: gemini-3.5-flash / gemini-3.1-flash-lite / gemini-3-flash)
5. Target Model + các provider có key khác (OpenAI, DeepSeek, Claude...)
6. Standard fallbacks (Gemini/OpenAI/FlatKey env keys)
```

Hệ thống Mặc định chạy MIỄN PHÍ trên OpenCode Zen Free Pool; key trả phí của khách hàng chỉ dùng khi toàn bộ pool free lỗi.

### Thuật toán Failover & Rotation (Xoay Vòng)

```text
[Khởi chạy phân tích AI]
         |
         v
[Kiểm tra API Key người dùng cấu hình]
   +-- Có khóa? --> Gọi Gateway / Model thương mại (GPT/Gemini/Claude...)
   +-- Không khóa? --> Gọi OpenCode Zen Free Gateway
         |
         v
[Thực thi HTTP Request]
   +-- THÀNH CÔNG --> Trả về dữ liệu phân tích cấu trúc / tin tức
   |
   +-- Lỗi kết nối / 429 / 400 / 401 (thất bại)
           |
           v
   [Auto Failover Engine]
           |
           v
   [Đọc Priority Queue (01 => 06 như trên)]
           |
           v
   [Tự chuyển sang provider kế tiếp]
           |
           v
   [Retry request]
```

**Cơ chế rotation**:
- Pool Gemini: xoay vòng 3 model để chia quota, tránh 429.
- Pool Free: di chuyển con trỏ mô hình sau mỗi lượt; model lỗi bị tạm khóa (cooldown) rồi được thử lại.

## Decision Pipeline Layers

```text
               +---------------------------------------------+
               |          1. TECHNICAL LAYER (tất định)      |
               |   - EMA20 vs EMA50 vs EMA200 Trend          |
               |   - RSI(14) Momentum Range                  |
               |   - ATR(14) Volatility Expansion            |
               +-----------------------+---------------------+
                                       | Proposal (BUY/SELL/NO_TRADE)
                                       v
               +---------------------------------------------+
               |        2. FUNDAMENTAL LAYER                 |
               |   - MT5 Real Economic Calendar Push         |
               |   - USD Macro News Analysis                 |
               |   - High Impact NFP/FOMC Sentiment          |
               +-----------------------+---------------------+
                                       | Confluence Score (0-100)
                                       v
               +---------------------------------------------+
               |        3. RISK SIZING LAYER                 |
               |   - Account Equity & Free Margin            |
               |   - Dynamic 1% Risk Sizing Formula          |
               |   - ATR Stop Loss & Take Profit             |
               +-----------------------+---------------------+
                                       | Sized Proposal
                                       v
               +---------------------------------------------+
               |         4. RISKGATE FILTER (Fail-Closed)     |
               |   - Policy Verification (15 điểm)           |
               |   - Position Limits & Spread Cap            |
               +-----------------------+---------------------+
                                       | Approved Intent
                                       v
                        CommandStore Ledger (SQLite)
```

## Công Thức Confluence Scoring

- **Trend Alignment (tối đa 40 điểm)**:
  - BUY: `EMA20 > EMA50` (+30), `EMA50 > EMA200` (+10).
  - SELL: `EMA20 < EMA50` (+30), `EMA50 < EMA200` (+10).
- **RSI Momentum (tối đa 30 điểm)**:
  - BUY: `50 <= RSI <= 70` (+30), `45 <= RSI < 50` (+20).
  - SELL: `30 <= RSI <= 50` (+30), `50 < RSI <= 55` (+20).
- **ATR Volatility (tối đa 30 điểm)**:
  - `ATR >= 4.0` (+20), `ATR < 4.0` (+10).
- **Final Confidence**: `min(98, max(50, Score))%`.

## Công Thức Sizing 1% Rủi Ro

$$\text{Risk Amount} = \text{Account Balance} \times 0.01$$

$$\text{SL Distance} = \max(3.0, \text{ATR} \times 1.5)$$

$$\text{Suggested Lot} = \text{Quantize}\left(\frac{\text{Risk Amount}}{\text{SL Distance} \times 100}, \text{Volume Step}\right)$$

## Vai Trò AI Trong Hệ Thống (2 vai trò)

1. **AI Copilot Assistant**: trả lời câu hỏi market/strategy/system qua chat dashboard; không tự mở lệnh.
2. **AI News & Calendar Analytics**: quét lịch kinh tế MT5, phát hiện tin high-impact (CPI, FOMC, NFP...) trước 15 phút công bố, khuyến cứu phòng thủ: khóa lệnh mới, dời SL về BE, đóng lệnh.

## Cấu Hình Trong .env (Tóm tắt AI)

| Biến | Mặc định | Ý nghĩa |
|------|----------|---------|
| `OPENCODE_BASE_URL` | `https://opencode.ai/zen/v1/chat/completions` | Endpoint Zen free |
| `QUANTAI_AI_MODEL` | `deepseek-v4-flash-free` | Model Mặc định |
| `OPENAI_API_KEY/BASE_URL` | trống | Key OpenAI (tùy chọn) |
| `GEMINI_API_KEY/BASE_URL` | trống | Key Gemini (tùy chọn) |
| `ZPLAY_API_KEY/BASE_URL` | trống | Key FlatKey (tùy chọn) |
| `GATEWAY_URL/GATEWAY_KEY` | trống | Router cá nhân (ưu tiên cao nhất) |

---

*Tài liệu thuộc dự án QuantAI - Nguyễn Quang Tú (QTusdev) | MIT License.*