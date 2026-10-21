"""EyeMouse 命令行入口：解析参数、设置 DPI、启动应用或摄像头自检。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, List, Optional

from eyemouse.calibration import CalibrationCancelled
from eyemouse.camera import Camera, CameraError
from eyemouse.config import AppConfig, load_config
from eyemouse.landmarks import LandmarkDetector
from eyemouse.ui import KEYPOINT_INDEXES

HOTKEY_HELP = """热键说明：
  F9  暂停/恢复（暂停后不再移动鼠标，只能用 F9 恢复）
  F10 退出
  F8  重新校准
  F7  开关点击功能
  F6  循环切换点击模式（blink_sequence -> dwell -> both -> none）
  F5  循环切换光标来源（eye 眼控 <-> head 面部朝向）
  F4  一键基准点校准（头控：把当前头姿设为零点，即屏幕中心）
"""


def set_dpi_awareness() -> None:
    """Windows 下设置 DPI 感知，避免分辨率获取错误；其他平台跳过。"""
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="EyeMouse：用普通摄像头追踪视线、以连续眨眼代替鼠标点击。",
    )
    parser.add_argument("--config", default="config.yaml", help="配置文件路径，默认 config.yaml")
    parser.add_argument("--recalibrate", action="store_true", help="强制重新校准")
    parser.add_argument(
        "--recalibrate-face",
        action="store_true",
        help="只重做个人面部标定（面部 3D 模板），沿用已有屏幕校准",
    )
    parser.add_argument("--dry-run", action="store_true", help="不真正控制鼠标，只打印动作")
    parser.add_argument("--no-window", action="store_true", help="不显示调试窗口")
    parser.add_argument("--camera-test", action="store_true", help="仅打开摄像头并显示关键点，不控制鼠标")
    parser.add_argument(
        "--pointer-source",
        choices=("eye", "hand", "hybrid"),
        default=None,
        help="覆盖 hand_control.pointer_source：eye 眼控 / hand 手控 / hybrid 混合",
    )
    parser.add_argument(
        "--hand-test",
        action="store_true",
        help="仅打开摄像头显示右手关键点与 gate 状态，不控制鼠标",
    )
    parser.add_argument(
        "--calibrate-camera",
        action="store_true",
        help="摄像头内参标定（ChArUco），只保存数值参数，不控制鼠标",
    )
    parser.add_argument(
        "--glasses-test",
        action="store_true",
        help="眼镜 ArUco 标记六自由度自检：只显示位姿，不控制鼠标、不触发点击",
    )
    parser.add_argument(
        "--write-charuco-board",
        nargs="?",
        const="data/charuco_board.png",
        default=None,
        metavar="PATH",
        help="导出可打印的 ChArUco 标定板 PNG（必须 100%% 实际尺寸打印），默认 data/charuco_board.png",
    )
    parser.add_argument(
        "--write-aruco-marker",
        nargs="?",
        const="data/aruco_marker_id0_30mm.png",
        default=None,
        metavar="PATH",
        help="导出眼镜 ArUco 单标记打印图纸（字典/id/黑框边长取自 glasses_tracking，必须 100%% 实际尺寸打印），默认 data/aruco_marker_id0_30mm.png",
    )
    parser.add_argument("--log-level", default=None, help="日志级别，如 DEBUG/INFO/WARNING")
    return parser


def camera_test(cfg: AppConfig, show_window: bool) -> int:
    """摄像头排错模式：显示关键点，ESC 退出；无摄像头时给出中文错误。"""
    import cv2

    camera = Camera(cfg.camera)
    detector = LandmarkDetector()
    try:
        camera.open()
    except CameraError as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        detector.close()
        return 1
    print("摄像头已打开。按 ESC 退出。若窗口未显示关键点，请检查光线与摄像头位置。")
    try:
        while True:
            frame = camera.read()
            if frame is None:
                continue
            face = detector.detect(frame)
            if face is not None:
                for index in KEYPOINT_INDEXES:
                    if index < len(face.pts_px):
                        px, py = face.pts_px[index]
                        cv2.circle(frame, (int(px), int(py)), 3, (0, 255, 255), -1)
            if not show_window:
                break
            try:
                cv2.imshow("EyeMouse Camera Test", frame)
                if (cv2.waitKey(1) & 0xFF) == 27:
                    break
            except cv2.error:
                print("[错误] 无法创建显示窗口，请在有图形界面的桌面环境运行。", file=sys.stderr)
                return 1
    finally:
        camera.release()
        detector.close()
        try:
            cv2.destroyAllWindows()
        except cv2.error:
            pass
    return 0


def hand_test(cfg: AppConfig, show_window: bool) -> int:
    """手部排错模式：显示右手 21 点与 gate 状态，ESC 退出；不动鼠标。"""
    import time as _time

    import cv2

    from eyemouse.hand_gesture import HAND_CONNECTIONS, OpenPalmGate, is_open_palm
    from eyemouse.hand_tracker import HandTracker

    camera = Camera(cfg.camera)
    try:
        tracker = HandTracker(mirror_handedness=cfg.hand_control.mirror_handedness)
    except Exception as exc:
        print(f"[错误] 手部检测初始化失败：{exc}", file=sys.stderr)
        return 1
    gate = OpenPalmGate(
        cfg.hand_control.enter_frames,
        cfg.hand_control.exit_frames,
        cfg.hand_control.lost_timeout,
    )
    try:
        camera.open()
    except CameraError as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        tracker.close()
        return 1
    print("手部自检已启动。张开右手手掌查看 Gate 状态，按 ESC 退出。")
    try:
        while True:
            frame = camera.read()
            if frame is None:
                continue
            hand = tracker.detect(frame, want="Right")
            present = hand is not None
            palm_open = bool(
                present
                and is_open_palm(
                    hand.pts_norm, cfg.hand_control.open_ratio, cfg.hand_control.finger_spread_min
                )
            )
            opened = gate.update(_time.perf_counter(), present, palm_open)
            if hand is not None:
                for start, end in HAND_CONNECTIONS:
                    cv2.line(
                        frame,
                        (int(hand.pts_px[start][0]), int(hand.pts_px[start][1])),
                        (int(hand.pts_px[end][0]), int(hand.pts_px[end][1])),
                        (0, 200, 255),
                        2,
                    )
                for point in hand.pts_px:
                    cv2.circle(frame, (int(point[0]), int(point[1])), 4, (255, 128, 0), -1)
            cv2.putText(
                frame,
                f"Right hand: {'yes' if present else 'no'}   palm open: {palm_open}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 255),
                2,
            )
            cv2.putText(
                frame,
                f"Gate: {'OPEN' if opened else 'CLOSED'}",
                (10, 62),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                (0, 255, 0) if opened else (0, 0, 255),
                2,
            )
            if not show_window:
                break
            try:
                cv2.imshow("EyeMouse Hand Test", frame)
                if (cv2.waitKey(1) & 0xFF) == 27:
                    break
            except cv2.error:
                print("[错误] 无法创建显示窗口，请在有图形界面的桌面环境运行。", file=sys.stderr)
                return 1
    finally:
        camera.release()
        tracker.close()
        try:
            cv2.destroyAllWindows()
        except cv2.error:
            pass
    return 0


def calibration_file(cfg: AppConfig) -> Path:
    """标定文件路径：配置里的相对路径按工作区根目录解析。"""
    path = Path(cfg.camera_calibration.file)
    if not path.is_absolute():
        path = Path(cfg.root or ".") / path
    return path


def write_charuco_board(cfg: AppConfig, target: str) -> int:
    """导出可打印的 ChArUco 标定板 PNG；不打开摄像头、不控制鼠标。"""
    from eyemouse.camera_calibration import CharucoBoardSpec, write_board_image

    board = CharucoBoardSpec.from_config(cfg.camera_calibration)
    path = Path(target)
    if not path.is_absolute():
        path = Path(cfg.root or ".") / path
    try:
        written = write_board_image(board, path)
    except Exception as exc:
        print(f"[错误] 生成标定板失败：{exc}", file=sys.stderr)
        return 1
    print(f"标定板已导出：{written}")
    print(
        f"板参数：{board.squares_x}x{board.squares_y} 方格，方格边长 {board.square_length_m * 1000:.2f} mm，"
        f"标记边长 {board.marker_length_m * 1000:.2f} mm，字典 {board.dictionary}"
    )
    print(
        f"整板物理尺寸：{board.squares_x * board.square_length_m * 1000:.1f} mm x "
        f"{board.squares_y * board.square_length_m * 1000:.1f} mm"
    )
    print("打印要求：必须 100% 实际尺寸，不要选“适合页面 / Fit to page”。")
    print("打印后用直尺实测若干方格边长；若与上面数值不符，请重新打印或同步修改 config.yaml。")
    return 0


def write_aruco_marker(cfg: AppConfig, target: str) -> int:
    """导出眼镜 ArUco 单标记打印图纸：只写 PNG，不打开摄像头、不控制鼠标、不改追踪逻辑。"""
    from eyemouse.marker_sheet import MarkerSheetSpec, render_marker_sheet, write_marker_sheet

    try:
        spec = MarkerSheetSpec.from_config(cfg)
        image, geometry = render_marker_sheet(spec)
    except Exception as exc:
        print(f"[错误] 生成 ArUco 标记图纸失败：{exc}", file=sys.stderr)
        return 1
    path = Path(target)
    if not path.is_absolute():
        path = Path(cfg.root or ".") / path
    try:
        written = write_marker_sheet(spec, path, image=image)
    except Exception as exc:
        print(f"[错误] 写出 ArUco 标记图纸失败：{exc}", file=sys.stderr)
        return 1
    width_mm = image.shape[1] / geometry.pixels_per_meter * 1000.0
    height_mm = image.shape[0] / geometry.pixels_per_meter * 1000.0
    print(f"标记图纸已导出：{written}")
    print(
        f"标记参数：字典 {spec.dictionary}，id={spec.marker_id}，"
        f"黑色外框边长 {geometry.marker_size_mm:.2f} mm，白边每侧 {geometry.quiet_margin_mm:.1f} mm"
    )
    print(
        f"整张纸物理尺寸：{width_mm:.1f} mm x {height_mm:.1f} mm"
        f"（渲染 {image.shape[1]}x{image.shape[0]} px，1 像素 = {1000.0 / geometry.pixels_per_meter:.4f} mm）"
    )
    print("打印要求：必须 100% 实际尺寸，不要选“适合页面 / Fit to page”，也不要镜像翻转。")
    print("量尺方式：")
    print(f"  1) 用真尺量图下方的参考条，必须是 {geometry.ruler_mm:.1f} mm；若不是，说明打印被缩放。")
    print(f"  2) 用真尺量黑色外框边长（黑边外缘到外缘），必须是 {geometry.marker_size_mm:.2f} mm。")
    print(
        f"  3) 把实测边长（单位：米）写入 config.yaml 的 glasses_tracking.marker_size_m"
        f"（当前配置 {spec.marker_size_m:.6f} m）；程序不猜尺寸。"
    )
    print("  4) 标记贴平、无反光，不遮挡眼睛与眨眼检测区域。")
    return 0


def calibrate_camera(cfg: AppConfig, show_window: bool) -> int:
    """摄像头内参标定：采集 ChArUco 视图并保存；不实例化鼠标控制、不触发点击。"""
    import cv2

    from eyemouse.camera_calibration import (
        CalibrationError,
        CharucoBoardSpec,
        calibrate_from_views,
        coverage_cells,
        detect_view,
        is_duplicate_view,
        save_calibration,
    )
    from eyemouse.ui import flip_display_point

    board = CharucoBoardSpec.from_config(cfg.camera_calibration)
    camera = Camera(cfg.camera)
    try:
        camera.open()
    except CameraError as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        return 1
    target = calibration_file(cfg)
    views: List[Any] = []
    saved = False
    print("摄像头内参标定（只保存数值参数，不保存图像，不控制鼠标）：")
    print(
        f"  标定板 {board.squares_x}x{board.squares_y}，方格 {board.square_length_m * 1000:.2f} mm，"
        f"标记 {board.marker_length_m * 1000:.2f} mm，字典 {board.dictionary}"
    )
    print(f"  目标：至少 {cfg.camera_calibration.min_views} 个不同倾角与画面位置的有效视图")
    print("  操作：空格=采集当前视图，C=完成标定并保存，R=清空重来，ESC/Q=退出")
    print(f"  内参保存位置：{target}")
    try:
        while True:
            raw = camera.read_raw()
            if raw is None:
                continue
            height, width = raw.shape[:2]
            gray = cv2.cvtColor(raw, cv2.COLOR_BGR2GRAY)
            view = detect_view(gray, board)
            hit: set = set()
            for item in views:
                hit |= coverage_cells(
                    item.corners, (width, height), cfg.camera_calibration.coverage_cells
                )
            if view is not None:
                hit |= coverage_cells(
                    view.corners, (width, height), cfg.camera_calibration.coverage_cells
                )
            if not show_window:
                print("[错误] 无窗口模式无法采集标定视图，请在图形界面下运行。", file=sys.stderr)
                return 1
            display = cv2.flip(raw, 1) if cfg.camera.mirror else raw.copy()
            if view is not None:
                for px, py in view.corners.reshape(-1, 2):
                    x, y = flip_display_point(float(px), float(py), width, cfg.camera.mirror)
                    cv2.circle(display, (int(round(x)), int(round(y))), 4, (0, 0, 255), -1)
            lines = [
                f"Views {len(views)}/{cfg.camera_calibration.min_views}   corners "
                f"{0 if view is None else view.count}",
                f"coverage {len(hit)}/{cfg.camera_calibration.coverage_cells ** 2} cells",
                "SPACE capture   C calibrate+save   R reset   ESC/Q quit",
            ]
            for index, text in enumerate(lines):
                cv2.putText(display, text, (8, 24 + index * 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            try:
                cv2.imshow("EyeMouse Camera Calibration", display)
            except cv2.error:
                print("[错误] 无法创建显示窗口，请在有图形界面的桌面环境运行。", file=sys.stderr)
                return 1
            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q"), ord("Q")):
                print("[提示] 已取消标定，未保存任何文件。")
                break
            if key in (ord("r"), ord("R")):
                views.clear()
                print("[提示] 已清空已采集视图。")
            if key == 32:
                if view is None or view.count < cfg.camera_calibration.min_corners_per_view:
                    print("[提示] 当前视图角点不足，请让标定板完整、清晰、对焦良好。")
                elif is_duplicate_view(
                    view.corners,
                    [item.corners for item in views],
                    (width, height),
                    cfg.camera_calibration.duplicate_distance,
                ):
                    print("[提示] 该视图与已有视图过于接近，请改变倾角或画面位置后再采集。")
                else:
                    views.append(view)
                    print(f"[采集] 第 {len(views)} 个视图，本视图角点 {view.count} 个。")
            if key in (ord("c"), ord("C")):
                required = max(int(cfg.camera_calibration.min_views), 3)
                if len(views) < required:
                    print(f"[提示] 视图不足：当前 {len(views)} 个，至少需要 {required} 个。")
                    continue
                try:
                    calibration, warnings = calibrate_from_views(
                        views,
                        (width, height),
                        board,
                        min_views=cfg.camera_calibration.min_views,
                        coverage_cells_n=cfg.camera_calibration.coverage_cells,
                        coverage_min_cells=cfg.camera_calibration.coverage_min_cells,
                    )
                except CalibrationError as exc:
                    print(f"[错误] {exc}", file=sys.stderr)
                    continue
                written = save_calibration(calibration, target)
                matrix = calibration.camera_matrix
                print(f"[完成] 已保存内参：{written}")
                print(
                    f"  分辨率 {calibration.image_size[0]}x{calibration.image_size[1]}，"
                    f"fx={matrix[0, 0]:.2f} fy={matrix[1, 1]:.2f} "
                    f"cx={matrix[0, 2]:.2f} cy={matrix[1, 2]:.2f}，视图 {calibration.num_views} 个"
                )
                print(
                    f"  整体重投影 RMS {calibration.rms_px:.3f} px"
                    "（只是重投影残差，不是参数协方差或绝对位姿精度）"
                )
                print(f"  覆盖网格 {calibration.coverage_cells_hit} 个")
                for warning in warnings:
                    print(f"[警告] {warning}")
                saved = True
                break
    finally:
        camera.release()
        try:
            cv2.destroyAllWindows()
        except cv2.error:
            pass
    return 0 if saved else 1


def print_glasses_stats(tracker: Any, stability: Any) -> None:
    """打印眼镜自检统计：有效帧率、有效比例、状态计数与静止抖动。"""
    summary = stability.summary()
    counts = ", ".join(f"{key}={value}" for key, value in sorted(tracker.stats.status_counts.items()))
    print(
        f"[统计] 有效帧率 {tracker.stats.tracking_fps():.1f} Hz，有效比例 "
        f"{tracker.stats.valid_ratio() * 100.0:.0f}%（共 {tracker.stats.frames} 帧）；"
        f"静止窗口 {summary['span_s']:.1f}s / {int(summary['samples'])} 样本："
        f"位置标准差 {summary['position_std_mm']:.2f} mm，旋转角抖动 {summary['rotation_std_deg']:.2f} 度；"
        f"状态计数 {counts or '无'}"
    )


def glasses_test(cfg: AppConfig, show_window: bool) -> int:
    """眼镜 ArUco 标记自检：只显示位姿，不创建鼠标控制、不注册点击动作。"""
    import cv2
    import time

    from eyemouse.camera_calibration import CalibrationError, load_calibration
    from eyemouse.glasses_tracker import GlassesTracker, StabilityStats
    from eyemouse.hotkeys import HotkeyManager
    from eyemouse.ui import draw_glasses_overlay

    path = calibration_file(cfg)
    try:
        calibration = load_calibration(path)
    except CalibrationError as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        print(
            "[提示] 尚无可用内参，请先执行：\n"
            "        .\\.venv\\Scripts\\python.exe main.py --write-charuco-board\n"
            "        .\\.venv\\Scripts\\python.exe main.py --calibrate-camera",
            file=sys.stderr,
        )
        return 1
    if (int(cfg.camera.width), int(cfg.camera.height)) != (
        int(calibration.image_size[0]),
        int(calibration.image_size[1]),
    ):
        print(
            f"[警告] 配置分辨率 {cfg.camera.width}x{cfg.camera.height} 与标定分辨率 "
            f"{calibration.image_size[0]}x{calibration.image_size[1]} 不一致，"
            "本模式将拒绝输出位姿，请重新运行 --calibrate-camera。",
            file=sys.stderr,
        )
    camera = Camera(cfg.camera)
    try:
        camera.open()
    except CameraError as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        return 1
    tracker = GlassesTracker(cfg.glasses_tracking, calibration)
    stability = StabilityStats(float(cfg.glasses_tracking.stability_window_s))
    mirror_display = bool(cfg.camera.mirror)
    hotkeys = HotkeyManager(cfg.safety)
    if show_window:
        hotkeys.start()
    print("眼镜标记自检已启动：不控制鼠标、不触发点击、不保存图像。")
    print(
        f"  标记 id={cfg.glasses_tracking.marker_id}，边长 {cfg.glasses_tracking.marker_size_m * 1000:.1f} mm"
        f"（必须实测），字典 {cfg.glasses_tracking.dictionary}"
    )
    print(f"  内参：{path}")
    print("  按键：ESC / q / F10 退出，m 切换显示镜像（只影响显示），r 重置，s 立即打印统计")
    last_report = time.time()
    try:
        while True:
            raw = camera.read_raw()
            if raw is None:
                continue
            now = time.perf_counter()
            pose = tracker.update(raw, now)
            if pose.valid and pose.translation_m is not None and pose.quaternion is not None:
                stability.push(now, pose.translation_m, pose.quaternion)
            if not show_window:
                break
            display = cv2.flip(raw, 1) if mirror_display else raw.copy()
            draw_glasses_overlay(
                display,
                pose,
                camera_matrix=calibration.camera_matrix,
                dist_coeffs=calibration.dist_coeffs,
                mirrored=mirror_display,
                axis_length_m=cfg.glasses_tracking.marker_size_m,
                stats=tracker.stats,
                stability=stability,
                extra_lines=("ESC/q/F10 quit  m mirror  r reset  s stats",),
            )
            try:
                cv2.imshow("EyeMouse Glasses Test", display)
            except cv2.error:
                print("[错误] 无法创建显示窗口，请在有图形界面的桌面环境运行。", file=sys.stderr)
                return 1
            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q"), ord("Q")):
                break
            if key in (ord("m"), ord("M")):
                mirror_display = not mirror_display
            if key in (ord("r"), ord("R")):
                tracker.reset()
                tracker.reset_stats()
                stability.reset()
                print("[提示] 已重置滤波器与统计。")
            if key in (ord("s"), ord("S")):
                print_glasses_stats(tracker, stability)
            if hotkeys.poll().quit:
                break
            if time.time() - last_report >= float(cfg.glasses_tracking.stats_period_s):
                last_report = time.time()
                print_glasses_stats(tracker, stability)
    finally:
        hotkeys.stop()
        camera.release()
        try:
            cv2.destroyAllWindows()
        except cv2.error:
            pass
    print_glasses_stats(tracker, stability)
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    """程序入口。"""
    args = build_parser().parse_args(argv)
    set_dpi_awareness()
    try:
        cfg = load_config(args.config)
    except (FileNotFoundError, ValueError) as exc:
        print(f"[错误] 配置读取失败：{exc}", file=sys.stderr)
        return 2
    if args.log_level:
        cfg.debug.log_level = args.log_level.upper()
    if args.pointer_source:
        cfg.hand_control.pointer_source = args.pointer_source
    if args.write_charuco_board:
        return write_charuco_board(cfg, args.write_charuco_board)
    if args.write_aruco_marker:
        return write_aruco_marker(cfg, args.write_aruco_marker)
    if args.calibrate_camera:
        return calibrate_camera(cfg, show_window=not args.no_window)
    if args.glasses_test:
        return glasses_test(cfg, show_window=not args.no_window)
    if args.camera_test:
        return camera_test(cfg, show_window=not args.no_window)
    if args.hand_test:
        return hand_test(cfg, show_window=not args.no_window)

    print(HOTKEY_HELP)
    from eyemouse.app import EyeMouseApp

    try:
        app = EyeMouseApp(
            cfg,
            dry_run=args.dry_run,
            show_window=not args.no_window,
            force_recalibrate=args.recalibrate,
            force_recalibrate_face=args.recalibrate_face,
        )
        return app.run()
    except CameraError as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        return 1
    except CalibrationCancelled as exc:
        print(f"[提示] {exc}", file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
