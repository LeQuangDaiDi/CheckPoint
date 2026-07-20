from __future__ import annotations

ATTACK_MODELS = {
    "STRIKER": {
        "name": "Striker-A1",
        "description": "Tên lửa tấn công tiêu chuẩn",
        "unit_cost": 1_200_000,
        "damage_factor": 1.0,
        "speed_factor": 1.0,
    },
    "MIRV": {
        "name": "Hydra-M4",
        "description": "Tên lửa mẹ mang nhiều đầu đạn con",
        "unit_cost": 4_800_000,
        "damage_factor": 0.92,
        "speed_factor": 0.94,
    },
    "JAMMER": {
        "name": "Phantom-EW",
        "description": "Tên lửa gây nhiễu radar",
        "unit_cost": 3_600_000,
        "damage_factor": 0.78,
        "speed_factor": 0.90,
    },
    "MIRV_JAMMER": {
        "name": "Hydra-Shadow",
        "description": "Tên lửa mẹ vừa tách đầu đạn vừa gây nhiễu",
        "unit_cost": 6_500_000,
        "damage_factor": 0.86,
        "speed_factor": 0.88,
    },
    "CHILD": {
        "name": "Viper-C",
        "description": "Đầu đạn con cơ động",
        "unit_cost": 420_000,
        "damage_factor": 0.46,
        "speed_factor": 1.02,
    },
}

DEFENSE_MODELS = {
    "PRECISION": {
        "name": "Aegis-LR",
        "description": "Đánh chặn chính xác cao, ưu tiên đầu đạn mẹ",
        "unit_cost": 2_100_000,
    },
    "AREA": {
        "name": "Skyburst-F",
        "description": "Đạn nổ vùng, tối ưu cho cụm mục tiêu",
        "unit_cost": 780_000,
    },
    "RAPID_A": {
        "name": "Falcon-CIWS",
        "description": "Đánh chặn nhanh đa mục tiêu tầm gần",
        "unit_cost": 240_000,
    },
    "RAPID_B": {
        "name": "Viper-CIWS",
        "description": "Đánh chặn nhanh dự phòng",
        "unit_cost": 290_000,
    },
}

CURRENCY = "$"
