# 🚀 FIXED STARTUP GUIDE - Windows PowerShell

## VẤN ĐỀ
Bạn đang chạy từ thư mục MT5 `Experts/tradeAI` thay vì thư mục project chính.

## CẤU TRÚC ĐÚNG

```
tradeAI/                    ← Thư mục gốc (chỗ này)
├── dashboard/               ← Backend #1 (MT5 + FastAPI)
│   ├── server.py
│   └── requirements.txt
├── web/                    ← Frontend (Next.js)
│   ├── app/
│   └── package.json
├── [working-dir]/          ← Backend #2 (SQLite + FastAPI)
│   └── trading_system/
│       ├── app/
│       │   ├── main.py
│       │   └── database/
│       └── requirements.txt
├── START_BACKEND.ps1       ← Script mới để chạy
└── START_BACKEND.bat       ← Script cũ
```

## CÁCH CHẠY ĐÚNG

### Cách 1: Dùng Script (Đề xuất)

```powershell
# 1. Mở PowerShell ở thư mục GỐC tradeAI
cd C:\path\to\tradeAI

# 2. Chạy script
.\START_BACKEND.ps1
```

### Cách 2: Chạy Thủ Công

```powershell
# === BACKEND #1: DASHBOARD (MT5) ===
cd C:\path\to\tradeAI\dashboard
python server.py

# Server chạy ở: http://localhost:8000
```

```powershell
# === BACKEND #2: TRADING SYSTEM (SQLite) ===
cd C:\path\to\tradeAI\[working-dir]\trading_system
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Server chạy ở: http://localhost:8000
```

### Cách 3: FRONTEND (Next.js)

```powershell
# Mở terminal mới
cd C:\path\to\tradeAI\web
npm install  # Chỉ cần chạy 1 lần
npm run dev

# Frontend chạy ở: http://localhost:3000
```

## TÌM THƯ MỤC GỐC

Nếu bạn không biết thư mục gốc ở đâu, chạy:

```powershell
# Tìm thư mục có file server.py
Get-ChildItem -Recurse -Filter "server.py" -ErrorAction SilentlyContinue | Select-Object -First 5 FullName

# Hoặc tìm thư mục dashboard
Get-ChildItem -Recurse -Filter "dashboard" -Directory -ErrorAction SilentlyContinue | Select-Object -First 5 FullName
```

## LỖI THƯỜNG GẶP

### Lỗi 1: "Cannot find path"
```
Cannot find path '...\working-dir\trading_system'
```
→ Bạn đang ở thư mục con. Cần `cd ..` lên thư mục gốc.

### Lỗi 2: "No module named 'app'"
```
ModuleNotFoundError: No module named 'app'
```
→ Bạn đang ở sai thư mục. Cần `cd` vào đúng `trading_system`.

### Lỗi 3: "Token '&&' is not valid"
```
The token '&&' is not a valid statement separator
```
→ Đang dùng PowerShell. Thay `&&` bằng `;` hoặc dùng script.

## KIỂM TRA ĐANG Ở ĐÚNG THƯ MỤC

```powershell
# Kiểm tra xem có file này không:
Test-Path ".\dashboard\server.py"
Test-Path ".\web\package.json"

# Nếu cả 2 đều True = đúng thư mục
```

## STARTUP SCRIPT ĐÃ TẠO

### START_BACKEND.ps1
- Auto-detect thư mục project
- Cho chọn backend 1 hoặc 2
- Tự động cd đúng thư mục

```powershell
# Cách dùng
.\START_BACKEND.ps1
# Chọn 1 = Dashboard (MT5)
# Chọn 2 = Trading System (SQLite)
```

## SAU KHI CHẠY THÀNH CÔNG

```
Backend:     http://localhost:8000
Frontend:    http://localhost:3000
API Docs:    http://localhost:8000/docs
Health:      http://localhost:8000/api/health
```

## NOTES

1. **MT5 cần chạy** để Dashboard hoạt động đầy đủ
2. **Backend #2** (SQLite) không cần MT5, dùng sample data
3. **Frontend** kết nối với Backend #1 mặc định
