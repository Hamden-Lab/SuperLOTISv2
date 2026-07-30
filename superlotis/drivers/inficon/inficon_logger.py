import argparse
import logging
import time

from superlotis.drivers.inficon.inficon import PxG55xRS485
from superlotis.tools.constants import PCG550_SERIAL_PORT, PSG550_SERIAL_PORT

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def build_gauges():
    gauge_specs = [
        ("PSG550", PSG550_SERIAL_PORT),
        ("PCG550", PCG550_SERIAL_PORT),
    ]

    gauges = {}
    for label, port in gauge_specs:
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
