import argparse
import csv
import logging
import sys
import time
from pathlib import Path
from typing import Dict, Optional

ROOT_DIR = Path(__file__).resolve().parents[0]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from superlotis.clients.inficon.inficon_client import (
    close_gauges,
    open_gauges,
    scan_serial_ports_for_inficon,
)
from superlotis.drivers.inficon.inficon import PxG55xRS485
from superlotis.drivers.pdu41001.pdu41001 import PDU41001
from superlotis.tools.constants import (
    PCG550_SERIAL_PORT,
    PSG550_SERIAL_PORT,
    PDU41001_IP_ADDRESS,
    PDU41001_PASSWORD,
    PDU41001_USER,
    VALVE_OUTLET,
)

try:
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


def find_gauge_ports() -> Dict[str, str]:
    found_ports = scan_serial_ports_for_inficon()
    if not found_ports:
        logger.warning("No Inficon gauges were detected by scan_serial_ports_for_inficon().")
    return found_ports


def open_inficon_gauges(pump_label: str, camera_label: str) -> Dict[str, PxG55xRS485]:
    found_ports = find_gauge_ports()
    gauges = open_gauges(found_ports)

    required_labels = [pump_label, camera_label]
    for label in required_labels:
        if label not in gauges:
            logger.warning("Gauge %s not found via scan. Trying fallback serial port.", label)
            if label == "PSG550":
                gauges[label] = PxG55xRS485(port=PSG550_SERIAL_PORT)
            elif label == "PCG550":
                gauges[label] = PxG55xRS485(port=PCG550_SERIAL_PORT)
            else:
                raise ValueError(f"Unsupported gauge label: {label}")
            logger.info("Opened fallback gauge %s on serial port %s", label, gauges[label].ser.port)

    return gauges


def init_plot(pump_label: str, camera_label: str):
    if not HAS_MATPLOTLIB:
        return None, None, None

    plt.ion()
    fig, ax = plt.subplots(figsize=(10, 5))
    pump_line, = ax.plot([], [], label=f"{pump_label} pressure")
    camera_line, = ax.plot([], [], label=f"{camera_label} pressure")
    ax.set_xlabel("Seconds from valve off")
    ax.set_ylabel("Pressure")
    ax.set_title("Inficon pump and camera gauge pressures")
    ax.legend()
    ax.grid(True)
    fig.tight_layout()
    return fig, ax, (pump_line, camera_line)


def update_plot(ax, lines, times, pump_values, camera_values):
    if not HAS_MATPLOTLIB or lines is None:
        return

    pump_line, camera_line = lines
    pump_line.set_data(times, pump_values)
    camera_line.set_data(times, camera_values)
    ax.relim()
    ax.autoscale_view()
    plt.draw()
    plt.pause(0.001)


def record_pressures(
    pump_label: str,
    camera_label: str,
    valve_outlet: int,
    interval: float,
    duration_seconds: float,
    output_path: Path,
):
    pdu = PDU41001(host=PDU41001_IP_ADDRESS, user=PDU41001_USER, password=PDU41001_PASSWORD)
    gauges: Dict[str, PxG55xRS485] = {}
    fig = ax = None
    lines = None

    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        logger.info("Connecting to PDU at %s", PDU41001_IP_ADDRESS)
        pdu.connect()
        logger.info("PDU connected")

        gauges = open_inficon_gauges(pump_label=pump_label, camera_label=camera_label)
        logger.info("Opened Inficon gauges: %s", ",".join(gauges.keys()))

        if HAS_MATPLOTLIB:
            fig, ax, lines = init_plot(pump_label, camera_label)
        else:
            logger.warning("matplotlib not installed. Live plotting is disabled.")

        headers = [
            "relative_seconds",
            "pump_label",
            "camera_label",
            "pump_pressure",
            "camera_pressure",
            "absolute_timestamp",
        ]
        with output_path.open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=headers)
            writer.writeheader()

            start_time = time.time()
            off_time: Optional[float] = None
            times = []
            pump_values = []
            camera_values = []

            end_time = start_time + duration_seconds
            next_sample_time = start_time

            while time.time() < end_time:
                loop_start = time.time()
                pump_pressure = gauges[pump_label].get_pressure_real()
                camera_pressure = gauges[camera_label].get_pressure_real()

                if off_time is None and loop_start >= start_time + 20.0:
                    logger.info("Turning off PDU outlet %d", valve_outlet)
                    pdu.power_off(outlet=valve_outlet)
                    off_time = loop_start
                    logger.info("Valve outlet %d turned off at %s", valve_outlet, time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(off_time)))

                relative_seconds = (
                    loop_start - off_time if off_time is not None else loop_start - (start_time + 20.0)
                )

                times.append(relative_seconds)
                pump_values.append(pump_pressure)
                camera_values.append(camera_pressure)

                row = {
                    "relative_seconds": f"{relative_seconds:.3f}",
                    "pump_label": pump_label,
                    "camera_label": camera_label,
                    "pump_pressure": f"{pump_pressure:.6g}",
                    "camera_pressure": f"{camera_pressure:.6g}",
                    "absolute_timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(loop_start)),
                }
                writer.writerow(row)
                csv_file.flush()

                logger.info(
                    "t=%.1fs pump=%s camera=%s",
                    relative_seconds,
                    pump_pressure,
                    camera_pressure,
                )

                update_plot(ax, lines, times, pump_values, camera_values)

                next_sample_time += interval
                sleep_duration = max(0.0, next_sample_time - time.time())
                time.sleep(sleep_duration)

            if off_time is None:
                logger.warning("Did not reach the 20 second off-delay before recording ended.")

        logger.info("Recording complete. CSV saved to %s", output_path)

    except Exception:
        logger.exception("Error during recording")
    finally:
        if gauges:
            close_gauges(gauges)
        try:
            pdu.close()
        except Exception:
            logger.exception("Error closing PDU connection")

        if HAS_MATPLOTLIB and fig is not None:
            plt.ioff()
            plt.show()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Record Inficon pump/camera pressures and control a PDU outlet.")
    parser.add_argument("--pump-gauge", default="PCG550", help="Label for the pump gauge (default: PCG550).")
    parser.add_argument("--camera-gauge", default="PSG550", help="Label for the camera gauge (default: PSG550).")
    parser.add_argument("--valve-outlet", type=int, default=VALVE_OUTLET, help="PDU outlet index for the valve.")
    parser.add_argument("--interval", type=float, default=5.0, help="Sampling interval in seconds.")
    parser.add_argument("--duration-hours", type=float, default=8.0, help="Total recording duration in hours.")
    parser.add_argument("--output", default="pressure_recording.csv", help="CSV output file path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    duration_seconds = args.duration_hours * 3600.0
    output_path = Path(args.output)
    record_pressures(
        pump_label=args.pump_gauge,
        camera_label=args.camera_gauge,
        valve_outlet=args.valve_outlet,
        interval=args.interval,
        duration_seconds=duration_seconds,
        output_path=output_path,
    )


if __name__ == "__main__":
    main()
