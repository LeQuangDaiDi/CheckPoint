# CheckPoint — Pixel Defense Command

Game phòng thủ 2D bằng Python và Pygame. Radar theo dõi mục tiêu, ưu tiên các đầu đạn gần căn cứ nhất, khóa độc quyền từng mục tiêu cho một bệ và so sánh chi phí giữa hai bên.

## Nâng cấp hiện tại

### Giao diện và bản đồ

- Bản đồ tăng từ `1280 × 720` lên `1600 × 900`.
- Toàn bộ bản đồ, căn cứ, bệ phóng, tên lửa và vụ nổ chuyển sang phong cách pixel.
- Căn cứ cũ được thay bằng trạm chỉ huy radar pixel-art.
- Bảng bên phải được chia rõ thành:
  - `ATTACK ARSENAL / ĐẠN TẤN CÔNG`
  - `DEFENSE BATTERIES / ĐẠN PHÒNG THỦ`
  - `BATTLE ECONOMY`

### Ưu tiên phòng thủ

- Radar sắp xếp mục tiêu theo thời gian còn lại trước khi chạm đất.
- Nếu thời gian bằng nhau, mục tiêu gần trạm radar hơn được xử lý trước.
- Mỗi mục tiêu chỉ có một bệ chủ quản và tối đa một đạn phòng thủ đang bay.
- Bệ khác chỉ tiếp quản khi bệ chủ quản hết đạn, mất nghiệm đánh chặn hoặc không kịp nạp lại.

### Tên lửa và quỹ đạo mới

Các loại tấn công:

- `Striker-A2`: tên lửa tiêu chuẩn tốc độ cao.
- `Hydra-M6`: tên lửa mẹ MIRV.
- `Phantom-EW2`: gây nhiễu và đổi hướng.
- `Hydra-Shadow X`: MIRV kết hợp gây nhiễu.
- `Raven-Cruise`: tên lửa hành trình bay thấp.
- `Meteor-Glide`: đầu đạn lượn tăng tốc pha cuối.
- `Viper-C2`: đầu đạn con siêu tốc.

Bảy quỹ đạo:

- `linear`
- `curved`
- `evasive`
- `weave`
- `dive`
- `cruise`
- `boost_glide`

Đầu đạn con sau khi tách có tốc độ cao hơn đầu đạn mẹ khoảng `1.55–1.84 lần`, đồng thời dùng quỹ đạo né tránh, dệt hoặc bổ nhào.

## Chạy game

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

## Điều khiển

| Phím | Chức năng |
|---|---|
| `D` | Mở/đóng bảng chi tiết |
| `Space` | Tạm dừng / tiếp tục |
| `A` | Bật/tắt phòng thủ tự động |
| `N` | Gọi wave tiếp theo |
| `R` | Chơi lại |
| `Esc` | Thoát |

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
