# CheckPoint

Game phòng thủ 2D viết bằng Python và Pygame. Hệ thống radar tự động phát hiện, đánh giá mức nguy hiểm, dự đoán điểm đánh chặn và phân bổ vũ khí theo vai trò.

## Tính năng hiện tại

### Tấn công

- Đạn có tốc độ, sát thương, bán kính nổ, độ chính xác và ba loại quỹ đạo.
- Mẫu tấn công dạng `số đạn mỗi lượt × số lượt`.
- Đầu đạn chính có thể tách thành 2–7 đầu đạn con ở độ cao ngẫu nhiên.
- Đầu đạn con bay tỏa ra nhiều hướng và có thể dùng quỹ đạo né tránh.
- Một số đầu đạn mang thiết bị gây nhiễu radar.
- Nhiễu mạnh làm giảm số kênh radar theo dõi và giảm độ chính xác của hỏa lực phòng thủ.

### Phòng thủ

- Radar có phạm vi quét, số kênh theo dõi, tốc độ xử lý và khả năng chống nhiễu ECCM.
- Radar ưu tiên theo dõi mục tiêu gần căn cứ nhất khi bị quá tải.
- `Precision`: tốc độ rất cao, độ chính xác cao, ưu tiên đầu đạn mẹ và mục tiêu gây nhiễu.
- `Flak`: bán kính nổ lớn, phù hợp đánh chặn cụm mục tiêu.
- `Rapid-A` và `Rapid-B`: tốc độ bắn cao, nhiều đạn, xử lý đầu đạn con và tấn công đa mục tiêu.
- AI tính điểm nguy hiểm dựa trên thời gian va chạm, tốc độ, sát thương, số đầu đạn con, mức gây nhiễu và quỹ đạo.
- AI ước lượng số đạn đánh chặn cần thiết và tránh dồn quá nhiều đạn vào cùng một mục tiêu.
- HUD hiển thị số mục tiêu radar theo dõi và mức nhiễu hiện tại.

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

Hệ thống giải phương trình bậc hai, chọn nghiệm dương nhỏ nhất rồi bắn tới `P + Vt`. Sai số cuối cùng được điều chỉnh theo độ chính xác vũ khí và chất lượng tín hiệu radar sau gây nhiễu.
