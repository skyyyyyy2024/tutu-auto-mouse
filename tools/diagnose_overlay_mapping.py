"""最小复现：校准前后同一组归一化关键点映射到像素坐标是否一致（合成数据，不开摄像头）。

背景
----
- ``main.py --camera-test`` 直接把人脸像素坐标画在摄像头帧上（身份映射，无缩放），显示正常；
- 调试叠加层先把帧缩放到 480x360 画布再画点。若缩放只按宽度算一个比例，而帧与画布
  长宽比不同，则纵向会整体偏移，表现为关键点显示在眼睛上方。

本脚本只用标准库（加上项目内的纯函数 ``eyemouse.ui.map_point_to_canvas``）复现并校验修复。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FRAME_W, FRAME_H = 1280, 720
CANVAS_W, CANVAS_H = 480, 360
NORMALIZED = [(0.50, 0.50), (0.35, 0.42), (0.65, 0.42)]


def to_frame_px(norm):
    """模拟 LandmarkDetector.detect：pts_px = pts_norm * [frame_w, frame_h]。"""
    return norm[0] * FRAME_W, norm[1] * FRAME_H


def camera_test_draw(norm):
    """--camera-test 路径：直接画在帧上，坐标即帧像素坐标。"""
    return to_frame_px(norm)


def legacy_overlay_draw(px, py):
    """修复前的叠加层公式：单一 scale = canvas_w / frame_w 同时乘 x、y。"""
    scale = CANVAS_W / float(FRAME_W)
    return px * scale, py * scale


def fixed_overlay_draw(px, py):
    """修复后的叠加层映射（来自 eyemouse.ui）；未修复时返回 None。"""
    try:
        from eyemouse.ui import map_point_to_canvas
    except Exception:
        return None
    return map_point_to_canvas(px, py, FRAME_W, FRAME_H, CANVAS_W, CANVAS_H)


def main() -> int:
    print(f"frame={FRAME_W}x{FRAME_H}  canvas={CANVAS_W}x{CANVAS_H}")
    print(f"correct_y_scale={CANVAS_H / FRAME_H:.4f}  legacy_scale={CANVAS_W / FRAME_W:.4f}")
    print()
    print("归一化       camera-test(帧px)      叠加层(旧)            叠加层(新)           旧相对y   新相对y")
    ok = True
    for norm in NORMALIZED:
        px, py = to_frame_px(norm)
        cam_x, cam_y = camera_test_draw(norm)
        leg_x, leg_y = legacy_overlay_draw(px, py)
        fixed = fixed_overlay_draw(px, py)
        fixed_text = f"({fixed[0]:6.1f},{fixed[1]:6.1f})" if fixed else "   (未修复)   "
        rel_leg = leg_y / CANVAS_H
        rel_fix = (fixed[1] / CANVAS_H) if fixed else float("nan")
        flag = ""
        if fixed is not None and abs(rel_fix - norm[1]) > 1e-6:
            flag = "  <-- 新映射仍不一致"
            ok = False
        print(
            f"{str(norm):12s} ({cam_x:7.1f},{cam_y:7.1f})   ({leg_x:6.1f},{leg_y:6.1f})   "
            f"{fixed_text}   {rel_leg:7.3f}   {rel_fix:7.3f}{flag}"
        )
    print()
    if fixed_overlay_draw(0.0, 0.0) is None:
        print("结论：尚未修复。旧缩放把纵向画成 frame_h * (canvas_w/frame_w) 比例，")
        print("      当帧为 16:9 而画布为 4:3 时，纵向偏差 = 25% 画布高（点显示在眼睛上方）。")
        print("      camera-test 用身份映射所以正常。")
        return 1
    print("结论：修复后叠加层与 camera-test 的相对位置一致（x/y 各自按帧与画布尺寸缩放）。")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
