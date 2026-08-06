# Coding Style & Formatting Rules

Mọi thao tác chỉnh sửa mã nguồn trong dự án phải tuân thủ nghiêm ngặt các quy tắc format sau:

1. **Prettier Compliance**: Tuân thủ chuẩn Prettier cho toàn bộ codebase (JS/TS/React/HTML/CSS/JSON/v.v.).
2. **JSX Formatting**:
   - JSX không được viết trên một dòng nếu dài.
   - Mỗi prop bắt buộc xuống dòng riêng biệt.
   - Không đặt nhiều component trên cùng một dòng.
3. **Object & Function Formatting**:
   - Mỗi object gồm nhiều thuộc tính phải được trình bày trên nhiều dòng.
   - Mỗi function khai báo/định nghĩa phải xuống dòng rõ ràng cho các tham số và body.
4. **Code Quality**:
   - Không sinh ra code minified hoặc gộp dòng.
   - Mã nguồn phải đạt chuẩn production, sạch sẽ, rõ ràng và dễ review trên GitHub.
5. **Post-edit Action**:
   - Sau khi hoàn thành chỉnh sửa bất kỳ file nào, luôn chạy linter/formatter (Prettier hoặc tương đương) trước khi kết thúc task.


6. **Quy tắc code**:

   - luôn phải code hiện thị dữ liệu thật dựa trên backkend thống nhất và đồng bộ theo thời gian thực với frontend.