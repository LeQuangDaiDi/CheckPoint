# CheckPoint

Game phòng thủ 2D viết bằng Python và Pygame. Radar tự động phát hiện, dự đoán điểm đánh chặn, phân bổ vũ khí và so sánh hiệu quả chi phí giữa bên tấn công và phòng thủ.

## Phân loại đạn trên màn hình

- **ATTACK MISSILES / WARHEADS**: tên lửa và đầu đạn tấn công, hiển thị bằng tam giác màu cam/đỏ.
- **DEFENSE INTERCEPTORS**: đạn đánh chặn phòng thủ, hiển thị bằng hình tròn màu xanh và đường dẫn hướng.
- HUD tách riêng số đã phóng, số đang bay và chi phí của hai bên.
- Nhấn `D` để mở bảng chi tiết riêng cho tấn công và phòng thủ.

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

## Khóa độc quyền bệ phòng thủ

Hệ thống hiện áp dụng quy tắc nghiêm ngặt:

1. Mỗi mục tiêu có một `uid` riêng.
2. Radar chọn đúng một bệ làm **bệ chủ quản** của mục tiêu.
3. Khi đã có một đạn đánh chặn đang bay, không bệ nào được bắn thêm vào mục tiêu đó.
4. Sau khi đạn đánh chặn kết thúc, bệ chủ quản được quyền thử lại nếu mục tiêu vẫn còn.
5. Bệ khác chỉ được tiếp quản khi bệ chủ quản hết đạn, không còn nghiệm đánh chặn, hoặc không thể nạp xong trước lúc mục tiêu va chạm.
6. Một mục tiêu luôn có tối đa một đạn phòng thủ đang bay.

HUD hiển thị số `Exclusive locks` và số lần `Takeovers` để kiểm tra việc phân công.

## Thống kê và chi phí

HUD hiển thị:

- Tổng số đạn tấn công đã phát sinh và số đang bay.
- Tổng số đạn phòng thủ đã bắn và số đang bay.
- Tổng chi phí tấn công và phòng thủ.
- Tỷ lệ chi phí tấn công/phòng thủ.
- Số mục tiêu đang được khóa cho từng bệ.

Nhấn `D` để mở bảng chi tiết:

- Số lượng từng loại tên lửa và đầu đạn tấn công.
- Số lượng từng loại đạn đánh chặn phòng thủ.
- Giá đơn vị và tổng chi phí từng loại.
- Tốc độ, độ chính xác, bán kính nổ, đạn còn lại và số mục tiêu đang giữ của từng bệ.

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
