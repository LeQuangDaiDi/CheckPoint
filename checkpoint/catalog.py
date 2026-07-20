from __future__ import annotations

ATTACK_MODELS = {
    "STRIKER": {
        "name": "Striker-A2",
        "description": "Tên lửa tấn công tiêu chuẩn tốc độ cao",
        "unit_cost": 1_350_000,
        "damage_factor": 1.0,
        "speed_factor": 1.10,
    },
    "MIRV": {
        "name": "Hydra-M6",
        "description": "Tên lửa mẹ mang nhiều đầu đạn siêu tốc",
        "unit_cost": 5_400_000,
        "damage_factor": 0.94,
        "speed_factor": 1.00,
    },
    "JAMMER": {
        "name": "Phantom-EW2",
        "description": "Tên lửa gây nhiễu và đổi hướng",
        "unit_cost": 4_100_000,
        "damage_factor": 0.82,
        "speed_factor": 0.98,
    },
    "MIRV_JAMMER": {
        "name": "Hydra-Shadow X",
        "description": "Tên lửa mẹ tách đầu đạn và gây nhiễu mạnh",
        "unit_cost": 7_200_000,
        "damage_factor": 0.90,
        "speed_factor": 0.96,
    },
    "CRUISE": {
        "name": "Raven-Cruise",
        "description": "Tên lửa hành trình bay thấp, bám địa hình",
        "unit_cost": 2_750_000,
        "damage_factor": 1.18,
        "speed_factor": 1.12,
    },
    "BOOST_GLIDE": {
        "name": "Meteor-Glide",
        "description": "Đầu đạn lượn tăng tốc và đổi hướng pha cuối",
        "unit_cost": 5_900_000,
        "damage_factor": 1.25,
        "speed_factor": 1.28,
    },
    "CHILD": {
        "name": "Viper-C2",
        "description": "Đầu đạn con siêu tốc, cơ động cao",
        "unit_cost": 520_000,
        "damage_factor": 0.48,
        "speed_factor": 1.48,
    },
}

DEFENSE_MODELS = {
    "PRECISION": {
        "name": "Aegis-LR2",
        "description": "Đánh chặn chính xác cao, ưu tiên đầu đạn mẹ",
        "unit_cost": 2_250_000,
    },
    "AREA": {
        "name": "Skyburst-F2",
        "description": "Đạn nổ vùng, tối ưu cho cụm mục tiêu",
        "unit_cost": 820_000,
    },
    "RAPID_A": {
        "name": "Falcon-CIWS2",
        "description": "Đánh chặn nhanh đa mục tiêu tầm gần",
        "unit_cost": 250_000,
    },
    "RAPID_B": {
        "name": "Viper-CIWS2",
        "description": "Đánh chặn nhanh dự phòng",
        "unit_cost": 305_000,
    },
}

CURRENCY = "$"
