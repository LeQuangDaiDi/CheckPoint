# CheckPoint

Game phòng thủ 2D viết bằng Python và Pygame. Radar tự động phát hiện, dự đoán điểm đánh chặn, phân bổ vũ khí và so sánh hiệu quả chi phí giữa bên tấn công và phòng thủ.

## Tên các loại đạn

### Tấn công

| Tên | Vai trò | Giá mô phỏng |
|---|---|---:|
| `Striker-A1` | Tên lửa tấn công tiêu chuẩn | $1.20M |
| `Hydra-M4` | Tên lửa mẹ mang nhiều đầu đạn | $4.80M |
| `Phantom-EW` | Tên lửa gây nhiễu radar | $3.60M |
| `Hydra-Shadow` | Tên lửa mẹ vừa tách đầu đạn vừa gây nhiễu | $6.50M |
| `Viper-C` | Đầu đạn con cơ động | $0.42M |

### Phòng thủ

| Tên | Vai trò | Giá mỗi phát |
|---|---|---:|
| `Aegis-LR` | Đánh chặn chính xác cao, ưu tiên đầu đạn mẹ | $2.10M |
| `Skyburst-F` | Nổ vùng, xử lý cụm mục tiêu | $0.78M |
| `Falcon-CIWS` | Đánh chặn nhanh đa mục tiêu | $0.24M |
| `Viper-CIWS` | Đánh chặn nhanh dự phòng | $0.29M |

Các mức giá chỉ phục vụ cân bằng và phân tích kinh tế trong game, không đại diện cho giá thiết bị thực tế.

## Tối ưu phân bổ đạn phòng thủ

- Mỗi mục tiêu có `uid` riêng.
- Đạn phòng thủ đang bay được ghi nhận là một cam kết đánh chặn.
- AI không bắn thêm khi xác suất tiêu diệt tích lũy đã đạt ngưỡng yêu cầu.
- Xác suất tích lũy được tính theo công thức `1 - tích các xác suất trượt`.
- Đầu đạn con giá trị thấp dùng ngưỡng khoảng 82%.
- Tên lửa thông thường dùng ngưỡng khoảng 92%.
- Đầu đạn mẹ lớn hoặc mục tiêu gây nhiễu dùng ngưỡng khoảng 97%.
- AI ưu tiên vũ khí rẻ nhất đáp ứng nhiệm vụ.
- `Aegis-LR` được giữ lại cho đầu đạn mẹ, mục tiêu gây nhiễu và mục tiêu có giá trị cao.
- `Falcon-CIWS` và `Viper-CIWS` xử lý đầu đạn con để giảm chi phí.
- `Skyburst-F` ưu tiên cụm mục tiêu nhờ bán kính nổ lớn.

## Thống kê và chi phí

HUD hiển thị:

- Tổng số đạn tấn công đã phát sinh.
- Tổng số đạn phòng thủ đã bắn.
- Tổng chi phí tấn công.
- Tổng chi phí phòng thủ.
- Tỷ lệ chi phí tấn công/phòng thủ.
- Tổng mục tiêu đánh chặn và số mục tiêu hiện tại.

Nhấn `D` để mở bảng chi tiết:

- Số lượng từng loại tên lửa và đầu đạn.
- Giá đơn vị và tổng chi phí từng loại.
- Tốc độ, độ chính xác, bán kính nổ và đạn còn lại của từng vũ khí phòng thủ.
- Bên có tổng chi phí thấp hơn và chênh lệch chi phí.

## Cài đặt

Yêu cầu Python 3.11 trở lên.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

## Điều khiển

| Phím | Chức năng |
|---|---|
| `D` | Mở/đóng bảng thông số và chi phí |
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
    ├── catalog.py
    ├── entities.py
    ├── game.py
    └── settings.py
```
