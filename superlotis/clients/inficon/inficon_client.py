import argparse
import logging
import socket
import socketserver
import sys
import threading
import time
from pathlib import Path
from typing import Dict, Optional

import serial.tools.list_ports

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from superlotis.drivers.inficon.inficon import PxG55xRS485

from superlotis.tools.constants import SLOTIS_STATUS_SERVER_IP_ADDRESS, SLOTIS_STATUS_SERVER_PORT

UDP_HOST = "0.0.0.0"
UDP_PORT = 5150
SCAN_TIMEOUT = 2.0

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


def normalize_label(value: str) -> str:
    return value.strip().upper()


def infer_gauge_label(product_name: str) -> Optional[str]:
    product_name = normalize_label(product_name)
    if "PCG550" in product_name:
        return "PCG550"
    if "PSG550" in product_name:
        return "PSG550"
    return None


def scan_serial_ports_for_inficon() -> Dict[str, Dict[str, str]]:
    ports = list(serial.tools.list_ports.comports())
    found: Dict[str, Dict[str, str]] = {}

    for port in ports:
        description = (port.description or "").strip()
        product = (port.product or "").strip()
        candidate_label = None

        if description:
            candidate_label = infer_gauge_label(description)
        if candidate_label is None and product:
            candidate_label = infer_gauge_label(product)

        if candidate_label is None:
            probe = None
            try:
                probe = PxG55xRS485(port.device, timeout=SCAN_TIMEOUT)
                product_name = probe.get_product_name()
                candidate_label = infer_gauge_label(product_name)
            except Exception:
                continue
            finally:
                if probe:
                    try:
                        probe.close()
                    except Exception:
                        pass

        if candidate_label:
            found[candidate_label] = {
                "device": port.device,
                "description": description,
                "product": product,
            }
            logger.info(
                "Detected Inficon gauge %s on %s (description=%s, product=%s)",
                candidate_label,
                port.device,
                description,
                product,
            )

    return found


def open_gauges(found_ports: Dict[str, Dict[str, str]]) -> Dict[str, PxG55xRS485]:
    gauges: Dict[str, PxG55xRS485] = {}
    for label, info in found_ports.items():
        try:
            gauges[label] = PxG55xRS485(port=info["device"], timeout=SCAN_TIMEOUT)
            logger.info("Opened gauge %s on %s", label, info["device"])
        except Exception:
            logger.exception("Failed to open Inficon gauge %s on %s", label, info["device"])
    return gauges


def close_gauges(gauges: Dict[str, PxG55xRS485]) -> None:
    for label, gauge in gauges.items():
        try:
            gauge.close()
            logger.info("Closed gauge %s", label)
        except Exception:
            logger.exception("Error closing gauge %s", label)


def build_status_response(gauges: Dict[str, PxG55xRS485]) -> str:
    if not gauges:
        return "No gauges available. Send 'probe' to rediscover."

    lines = ["Available gauges:"]
    for label, gauge in gauges.items():
        try:
            product = gauge.get_product_name()
            serial = gauge.get_serial_number()
            lines.append(f"{label}: {product} ({serial})")
        except Exception:
            lines.append(f"{label}: error reading info")
    return "\n".join(lines)


def process_command(command: str, server) -> bytes:
    command = command.strip()
    if not command:
        return b"Empty command"

    lower = command.lower()
    if lower == "list":
        return build_status_response(server.gauges).encode("utf-8")

    if lower == "probe":
        close_gauges(server.gauges)
        found = scan_serial_ports_for_inficon()
        server.gauges = open_gauges(found)
        return build_status_response(server.gauges).encode("utf-8")

    parts = lower.split()
    if len(parts) < 3 or parts[0] != "get":
        return b"Valid commands: list, probe, get <PCG550|PSG550> <pressure|fixed|serial|product>"

    _, gauge_name, field = parts[:3]
    gauge_name = gauge_name.upper()
    gauge = server.gauges.get(gauge_name)
    if gauge is None:
        return f"Gauge {gauge_name} not found. Send 'probe' first.".encode("utf-8")

    try:
        if field in ("pressure", "real", "value"):
            return str(gauge.get_pressure_real()).encode("utf-8")
        if field in ("fixed", "fixedpressure"):
            return str(gauge.get_pressure_fixed()).encode("utf-8")
        if field == "serial":
            return str(gauge.get_serial_number()).encode("utf-8")
        if field == "product":
            return gauge.get_product_name().encode("utf-8")
    except Exception:
        logger.exception("Error reading %s from %s", field, gauge_name)
        return f"Error reading {field} from {gauge_name}".encode("utf-8")

    return b"Unknown field. Use pressure, fixed, serial, or product."


def stream_measurements(gauges: Dict[str, PxG55xRS485], target_host: str, target_port: int, interval: float) -> None:
    while True:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.connect((target_host, target_port))
                logger.info("Starting pressure stream to %s:%s every %.1f seconds over TCP", target_host, target_port, interval)

                while True:
                    if not gauges:
                        logger.warning("No gauges to stream. Waiting before retrying.")
                        time.sleep(interval)
                        continue

                    for label, gauge in gauges.items():
                        try:
                            pressure = gauge.get_pressure_real()
                            payload = f"set {label}_pressure {pressure:.6g}".encode("utf-8")
                            sock.sendall(payload)
                            time.sleep(0.1)  # Small delay to avoid overwhelming the server
                        except Exception:
                            logger.exception("Failed to read pressure from %s", label)
                            continue

                    time.sleep(interval)
        except Exception:
            logger.exception("TCP pressure stream connection failed to %s:%s", target_host, target_port)
            time.sleep(interval)


class InficonUDPHandler(socketserver.BaseRequestHandler):
    def handle(self):
        data = self.request[0].strip()
        udp_socket = self.request[1]
        command = data.decode("utf-8", errors="replace")

        logger.info("UDP request from %s: %s", self.client_address, command)
        response = process_command(command, self.server)
        udp_socket.sendto(response, self.client_address)


class InficonUDPServer(socketserver.ThreadingUDPServer):
    allow_reuse_address = True

    def __init__(self, server_address, handler_class, gauges: Dict[str, PxG55xRS485]):
        super().__init__(server_address, handler_class)
        self.gauges = gauges


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inficon client with optional UDP server and streaming mode.")
    parser.add_argument("--server-host", default=UDP_HOST, help="Local UDP server host to listen on.")
    parser.add_argument("--server-port", type=int, default=UDP_PORT, help="Local UDP server port to listen on.")
    parser.add_argument("--stream-host", default="localhost", help="Remote UDP server host to stream pressure measurements to.")
    parser.add_argument("--stream-port", type=int, default=SLOTIS_STATUS_SERVER_PORT, help="Remote UDP server port to stream pressure measurements to.")
    parser.add_argument("--interval", type=float, default=1.0, help="Pressure measurement interval in seconds.")
    return parser.parse_args()

#SLOTIS_STATUS_SERVER_IP_ADDRESS

def main() -> None:
    args = parse_args()
    found_ports = scan_serial_ports_for_inficon()
    gauges = open_gauges(found_ports)

    if not gauges:
        logger.warning("No Inficon gauges found during startup. Use UDP command 'probe' after launch or check connections.")

    stream_thread = None
    if args.stream_host and args.stream_port:
        stream_thread = threading.Thread(
            target=stream_measurements,
            args=(gauges, args.stream_host, args.stream_port, args.interval),
            daemon=True,
        )
        stream_thread.start()

    if args.server_host and args.server_port:
        with InficonUDPServer((args.server_host, args.server_port), InficonUDPHandler, gauges) as server:
            logger.info("Inficon UDP command server listening on %s:%s", args.server_host, args.server_port)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                logger.info("Stopping Inficon UDP command server")
            finally:
                close_gauges(server.gauges)
    else:
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            logger.info("Stopping Inficon client")
        finally:
            close_gauges(gauges)


if __name__ == "__main__":
    main()

