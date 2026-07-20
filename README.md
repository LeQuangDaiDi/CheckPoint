# CheckPoint

Game phòng thủ 2D viết bằng Python và Pygame. Hệ thống phòng thủ tự động phân tích mục tiêu, dự đoán quỹ đạo bay, chọn điểm đánh chặn và sử dụng vũ khí có tốc độ, độ chính xác và bán kính nổ phù hợp.

## Tính năng MVP

- Đạn tấn công có tốc độ, sát thương, bán kính nổ và độ chính xác.
- Ba loại quỹ đạo: thẳng, cong và né tránh.
- Mẫu tấn công dạng `số đạn mỗi lượt × số lượt`, ví dụ `2 × 2` tạo tổng cộng 4 viên.
- Thuật toán giải phương trình đánh chặn cho mục tiêu bay tuyến tính.
- AI xếp hạng mức độ nguy hiểm và tránh nhiều vũ khí cùng ưu tiên một mục tiêu.
- Ba vũ khí phòng thủ: Precision, Flak và Interceptor.
- Bán kính nổ có thể phá hủy nhiều viên đạn trong cùng cụm.
- Wave tăng dần độ khó, điểm số, máu căn cứ và lượng đạn giới hạn.

## Cài đặt

Yêu cầu Python 3.11 trở lên.

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

Linux/macOS:

```bash
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Điều khiển

| Phím | Chức năng |
|---|---|
| `Space` | Tạm dừng / tiếp tục |
| `A` | Bật hoặc tắt phòng thủ tự động |
| `N` | Gọi đợt tấn công tiếp theo |
| `R` | Chơi lại |
| `Esc` | Thoát game |

## Cấu trúc

```text
CheckPoint/
├── main.py
├── requirements.txt
└── checkpoint/
    ├── algorithms.py
    ├── entities.py
    ├── game.py
    └── settings.py
```

## Thuật toán đánh chặn

Với vị trí mục tiêu `P`, vận tốc mục tiêu `V`, vị trí vũ khí `D`, tốc độ đạn phòng thủ `S` và thời gian `t`:

```text
|P + Vt - D|² = S²t²
```

Hệ thống giải phương trình bậc hai, chọn nghiệm dương nhỏ nhất rồi bắn tới `P + Vt`.
