# QuantAI - Autonomous Trading Engine (ATE) | Kho Tài Liệu Dự Án

Trang mục lục chính thức của toàn bộ hệ thống tài liệu dự án **QuantAI - Autonomous Trading Engine for XAUUSD (Gold)**.

## Giới thiệu

QuantAI (hay ATE - Autonomous Trading Engine) là một hệ thống giao dịch tự động hoàn chỉnh cho thị trường Vàng (XAUUSD) trên nền tảng MetaTrader 5, kết hợp ba phân hệ:

1. **MQL5 Expert Advisor** (`QuantAI_XAUUSD.mq5`) - phân hệ thực thi lệnh duy nhất trên MetaTrader 5.
2. **FastAPI Backend** (`dashboard/`) - trung tâm phân tích định lượng, AI Engine đa nhà cung cấp và lớp kiểm soát rủi ro.
3. **Next.js Web Dashboard** (`web/`) - giao diện Bloomberg Terminal để giám sát và điều khiển.

## Bản quyền

- **Tác giả / Lead Developer**: Nguyễn Quang Tú (QTusdev)
- **GitHub Repository**: https://github.com/qtu11/Autonomous-Trading-Engine
- **GitHub Profile**: https://github.com/qtu11
- **Giấy phép**: MIT License - xem chi tiết tại [COPYRIGHT.md](./COPYRIGHT.md) và file `LICENSE` ở thư mục gốc.

---

## Hướng dẫn đọc tài liệu

Nếu bạn là người mới tiếp cận dự án, hãy đọc theo thứ tự sau:

| Bước | Tài liệu | Nội dung |
|------|----------|----------|
| 1 | [FEATURES.md](./FEATURES.md) | Tổng quan tính năng và khả năng toàn hệ thống |
| 2 | [ARCHITECTURE.md](./ARCHITECTURE.md) | Kiến trúc hệ thống 3 phân hệ |
| 3 | [DATA_FLOW.md](./DATA_FLOW.md) | Luồng dữ liệu & vòng đời lệnh giao dịch |
| 4 | [TRADING_METHODS.md](./TRADING_METHODS.md) | 5 phương pháp giao dịch & 72+ mẫu hình thị trường |
| 5 | [ATE_DOCUMENTATION.md](./ATE_DOCUMENTATION.md) | Tài liệu kỹ thuật tổng hợp (AI Engine, định lượng, tích hợp) |
| 6 | [AI_PIPELINE.md](./AI_PIPELINE.md) | Kiến trúc đa mô hình AI & định tuyến failover |
| 7 | [RISK_ANALYSIS.md](./RISK_ANALYSIS.md) | Mô hình mối đe dọa & bộ lọc rủi ro 15 điểm |
| 8 | [OPERATION_GUIDE.md](./OPERATION_GUIDE.md) | Hướng dẫn vận hành thực tế |

## Thư mục tài liệu chi tiết

### Kiến trúc & Thiết kế hệ thống

| File | Nội dung |
|------|----------|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Sơ đồ kiến trúc tổng quan, ranh giới trách nhiệm từng module |
| [MODULES.md](./MODULES.md) | Phân rã chi tiết từng module theo thư mục mã nguồn |
| [DATA_FLOW.md](./DATA_FLOW.md) | Chu trình dữ liệu từ tick MT5 đến lệnh khớp và phản hồi UI |
| [DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md) | Cấu trúc cơ sở dữ liệu SQLite WAL (Sổ cái lệnh) & cấu hình bền vững |

### Trí tuệ nhân tạo & Chiến lược giao dịch

| File | Nội dung |
|------|----------|
| [AI_PIPELINE.md](./AI_PIPELINE.md) | Multi-AI Provider Engine, chuỗi failover & công thức confluence |
| [ATE_DOCUMENTATION.md](./ATE_DOCUMENTATION.md) | Tài liệu kỹ thuật tổng hợp: AI Engine, logic định lượng, tích hợp |
| [TRADING_METHODS.md](./TRADING_METHODS.md) | 5 phương pháp: Price Action, SMC, ICT, Sniper, Ultra Confluence |
| [winrate_and_strategy_evaluation.md](./winrate_and_strategy_evaluation.md) | Phân tích xác suất đạt win rate 80%+ và điều kiện duy trì |

### Giao thức & API

| File | Nội dung |
|------|----------|
| [MT5_PROTOCOL.md](./MT5_PROTOCOL.md) | Giao thức liên lạc EA - Backend (claim, receipt, telemetry) |
| [API_SPEC.md](./API_SPEC.md) | Đặc tả toàn bộ REST API và WebSocket |

### Rủi ro, Hiệu năng & Giao diện

| File | Nội dung |
|------|----------|
| [RISK_ANALYSIS.md](./RISK_ANALYSIS.md) | Ma trận rủi ro - mối đe dọa & cơ chế interlock |
| [PERFORMANCE_PLAN.md](./PERFORMANCE_PLAN.md) | Mục tiêu về độ trễ và các chiến lược tối ưu hiệu năng |
| [UI_GUIDELINES.md](./UI_GUIDELINES.md) | Design system - phong cách Bloomberg Trading Desk |

### Vận hành & Bản quyền

| File | Nội dung |
|------|----------|
| [OPERATION_GUIDE.md](./OPERATION_GUIDE.md) | Hướng dẫn cài đặt, cấu hình, vận hành & các bước troubleshooting |
| [COPYRIGHT.md](./COPYRIGHT.md) | Thông tin bản quyền, giấy phép MIT & đạo hành sử dụng |
| [KE_HOACH_XAY_DUNG_TICH_HOP_4_PHUONG_PHAP.md](./KE_HOACH_XAY_DUNG_TICH_HOP_4_PHUONG_PHAP.md) | Kế hoạch xây dựng & tích hợp 4-5 phương pháp giao dịch (tài liệu kế hoạch) |

---

## Tài liệu liên quan khác

| File | Vị trí | Nội dung |
|------|--------|----------|
| `README.md` | Thư mục gốc | Giới thiệu nhanh dự án cho người mới |
| `MARKET_ANALYSIS_SPEC.md` | Thư mục gốc | Đặc tả chi tiết Market Analysis Engine (detection & validation) |
| `LICENSE` | Thư mục gốc | Giấy phép MIT đầy đủ |
| `Cloudlocal/CLOUDLOCAL_STANDARD.md` | `Cloudlocal/` | Chuẩn triển khai cloud local (Vercel + Nginx) |
| `Cloudlocal/README.md` | `Cloudlocal/` | Hướng dẫn triển khai cloudlocal |

---

*Tài liệu được duy trì bởi đội ngũ QuantAI - tác giả Nguyễn Quang Tú (QTusdev).*