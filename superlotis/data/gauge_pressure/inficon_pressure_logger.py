import csv
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from superlotis.drivers.inficon.inficon import PxG55xRS485, discover_gauge_ports


def build_output_path(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y%m%d")
    return output_dir / f"gauge_pressures_{today}.csv"


def open_gauges() -> Dict[str, PxG55xRS485]:
    discovered_ports = discover_gauge_ports(timeout=2.0)
    if not discovered_ports:
        raise RuntimeError("No Inficon gauges were detected on available serial ports.")

    gauges: Dict[str, PxG55xRS485] = {}
    for label, port in discovered_ports.items():
        try:
            gauges[label] = PxG55xRS485(port=port, timeout=2.0)
            print(f"Connected {label} on {port}")
        except Exception as exc:
            print(f"Could not open {label} on {port}: {exc}")

    if not gauges:
        raise RuntimeError("No Inficon gauges could be opened.")

    return gauges


def main() -> None:
    output_dir = Path(__file__).resolve().parent
    output_path = build_output_path(output_dir)
    gauges = open_gauges()

    labels = sorted(gauges.keys())
    fieldnames = ["timestamp", "elapsed_seconds", *labels]

    with output_path.open("a", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        if csv_file.tell() == 0:
            writer.writeheader()

        start_time = time.time()
        print(f"Logging to {output_path}")
        print("Press Ctrl+C to stop.")

        try:
            while True:
                row = {
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                    "elapsed_seconds": round(time.time() - start_time, 2),
                }

                for label in labels:
                    gauge = gauges[label]
                    try:
                        row[label] = gauge.get_pressure_real()
                    except Exception as exc:
                        row[label] = f"ERROR: {exc}"

                writer.writerow(row)
                csv_file.flush()
                print(row)
                time.sleep(5.0)
        except KeyboardInterrupt:
            print("Stopped by keyboard interrupt.")
        finally:
            for gauge in gauges.values():
                try:
                    gauge.close()
                except Exception:
                    pass


if __name__ == "__main__":
    main()
