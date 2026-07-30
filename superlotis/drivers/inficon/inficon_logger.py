import argparse
import logging
import time

from superlotis.drivers.inficon.inficon import PxG55xRS485, discover_gauge_ports

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def build_gauges():
    discovered_ports = discover_gauge_ports(timeout=2.0)
    if not discovered_ports:
        raise RuntimeError("No Inficon gauges could be identified on any available serial port.")

    gauges = {}
    for label, port in discovered_ports.items():
        try:
            gauges[label] = PxG55xRS485(port=port, timeout=2.0)
            logger.info("Connected %s on %s", label, port)
        except Exception as exc:
            logger.exception("Could not open %s on %s: %s", label, port, exc)

    if not gauges:
        raise RuntimeError("No Inficon gauges could be opened.")

    return gauges


def main() -> None:
    parser = argparse.ArgumentParser(description="Continuously log Inficon gauge pressures to the terminal.")
    parser.add_argument("--interval", type=float, default=1.0, help="Seconds between pressure reads.")
    args = parser.parse_args()

    gauges = build_gauges()

    try:
        while True:
            for label, gauge in gauges.items():
                try:
                    pressure = gauge.get_pressure_real()
                    logger.info("%s pressure = %.6f", label, pressure)
                except Exception as exc:
                    logger.exception("Failed to read pressure from %s: %s", label, exc)

            time.sleep(args.interval)
    except KeyboardInterrupt:
        logger.info("Stopping Inficon pressure logger")
    finally:
        for gauge in gauges.values():
            try:
                gauge.close()
            except Exception:
                pass


if __name__ == "__main__":
    main()
