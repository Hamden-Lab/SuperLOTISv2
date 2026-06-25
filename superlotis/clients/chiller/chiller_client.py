import argparse
import datetime
import logging
import socket
import socketserver
import sys
import threading
import time
from pathlib import Path
from typing import List

from superlotis.drivers.chiller.chiller import TCubeChiller
from superlotis.tools.constants import (
    SLOTIS_SCHEDULER_IP_ADDRESS,
    SLOTIS_SCHEDULER_PORT,
    SLOTIS_STATUS_SERVER_IP_ADDRESS,
    SLOTIS_STATUS_SERVER_PORT,
)

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


def parse_schedule_time(token: str) -> float:
    token = token.strip().lower()
    if token in ("now", "immediate"):
        return 0.0

    if token.startswith("+"):
        return float(token[1:])

    try:
        return float(token)
    except ValueError:
        pass

    try:
        dt = datetime.datetime.fromisoformat(token)
        now = datetime.datetime.now(dt.tzinfo)
        return max((dt - now).total_seconds(), 0.0)
    except ValueError:
        pass

    try:
        parts = token.split(":")
        if len(parts) == 3:
            hour, minute, second = map(int, parts)
            now = datetime.datetime.now()
            target = now.replace(hour=hour, minute=minute, second=second, microsecond=0)
            if target < now:
                target += datetime.timedelta(days=1)
            return (target - now).total_seconds()
    except Exception:
        pass

    raise ValueError(f"Invalid time token: {token}")


def execute_chiller_command(chiller: TCubeChiller, command_tokens: List[str]) -> str:
    if not command_tokens:
        return "No command provided"

    cmd = command_tokens[0].lower()
    if cmd == "get":
        if len(command_tokens) < 2:
            return "Missing get parameter"

        param = command_tokens[1].lower()
        try:
            if param in ("temperature", "real", "actual"):
                return str(chiller.get_temperature())
            if param in ("setpoint", "set", "temperature_setpoint"):
                return str(chiller.get_setpoint())
            return f"Unknown get parameter: {param}"
        except Exception:
            logger.exception("Failed to read %s", param)
            return f"Error reading {param}"

    if cmd == "set":
        if len(command_tokens) < 3:
            return "Missing set parameter or value"

        param = command_tokens[1].lower()
        value = command_tokens[2]
        try:
            if param in ("temperature", "setpoint", "set"):
                chiller.set_setpoint(float(value))
                return f"Setpoint set to {value}"
            return f"Unknown set parameter: {param}"
        except Exception:
            logger.exception("Failed to set %s to %s", param, value)
            return f"Error setting {param}"

    if cmd == "run":
        try:
            chiller.run()
            return "Chiller started"
        except Exception:
            logger.exception("Failed to run chiller")
            return "Error starting chiller"

    if cmd == "stop":
        try:
            chiller.stop()
            return "Chiller stopped"
        except Exception:
            logger.exception("Failed to stop chiller")
            return "Error stopping chiller"

    return f"Unknown command: {cmd}"


def schedule_command(chiller: TCubeChiller, line: str) -> str:
    line = line.strip()
    if not line:
        return "Empty line"

    parts = line.split()
    if len(parts) < 2:
        return f"Invalid line: {line}"

    time_token = parts[0]
    command_tokens = parts[1:]

    try:
        delay = parse_schedule_time(time_token)
    except ValueError as exc:
        return str(exc)

    if delay <= 0:
        result = execute_chiller_command(chiller, command_tokens)
        logger.info("Executed immediately: %s => %s", line, result)
        return f"EXECUTED: {result}"

    def task() -> None:
        result = execute_chiller_command(chiller, command_tokens)
        logger.info("Scheduled command executed after %.1f sec: %s => %s", delay, line, result)

    timer = threading.Timer(delay, task)
    timer.daemon = True
    timer.start()
    return f"SCHEDULED in {delay:.1f}s: {line}"


def process_scheduler_payload(payload: bytes, chiller: TCubeChiller) -> bytes:
    message = payload.decode("utf-8", errors="replace")
    lines = [line for line in message.splitlines() if line.strip()]
    if not lines:
        return b"No scheduler commands received"

    responses = []
    for line in lines:
        response = schedule_command(chiller, line)
        responses.append(response)
    return "\n".join(responses).encode("utf-8")


class ChillerUDPHandler(socketserver.BaseRequestHandler):
    def handle(self):
        data = self.request[0].strip()
        udp_socket = self.request[1]
        logger.info("Scheduler request from %s: %s", self.client_address, data.decode("utf-8", errors="replace"))
        response = process_scheduler_payload(data, self.server.chiller)
        udp_socket.sendto(response, self.client_address)


class ChillerUDPServer(socketserver.ThreadingUDPServer):
    allow_reuse_address = True

    def __init__(self, server_address, handler_class, chiller: TCubeChiller):
        super().__init__(server_address, handler_class)
        self.chiller = chiller


def status_stream(chiller: TCubeChiller, status_host: str, status_port: int, interval: float, stop_event: threading.Event) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        logger.info("Starting chiller status stream to %s:%s every %.1f seconds", status_host, status_port, interval)
        while not stop_event.is_set():
            try:
                setpoint = chiller.get_setpoint()
                temperature = chiller.get_temperature()
                payload = (
                    f"set temperature {setpoint:.1f}\n"
                    f"real temperature {temperature:.1f}\n"
                ).encode("utf-8")
                sock.sendto(payload, (status_host, status_port))
                logger.debug("Sent chiller status update to %s:%s", status_host, status_port)
            except Exception:
                logger.exception("Failed to send chiller status update")

            stop_event.wait(interval)


def tcp_temperature_stream(chiller: TCubeChiller, status_host: str, status_port: int, interval: float, stop_event: threading.Event) -> None:
    """Send the current chiller temperature to the status server over TCP every `interval` seconds.

    The message format is: "set chiller_temp {T}" (single line). The function will attempt
    to reconnect on failure and stop when `stop_event` is set.
    """
    logger.info("Starting chiller TCP temperature stream to %s:%s every %.1f seconds", status_host, status_port, interval)
    sock = None
    while not stop_event.is_set():
        try:
            if sock is None:
                sock = socket.create_connection((status_host, status_port), timeout=5)
            temperature = chiller.get_temperature()
            payload = f"set chiller_temp {temperature:.1f}".encode("utf-8")
            try:
                sock.sendall(payload + b"\n")
                logger.debug("Sent chiller TCP temperature to %s:%s", status_host, status_port)
            except Exception:
                # Reset socket to attempt reconnect on next loop
                logger.exception("Failed to send over TCP, will reconnect")
                try:
                    sock.close()
                except Exception:
                    pass
                sock = None
        except Exception:
            logger.exception("TCP connection error for chiller temperature stream")
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass
            sock = None

        stop_event.wait(interval)

    if sock:
        try:
            sock.close()
        except Exception:
            pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Chiller client with scheduler listener and status updates.")
    parser.add_argument("--serial-port", required=True, help="Serial port for the chiller device.")
    parser.add_argument("--scheduler-host", default=SLOTIS_SCHEDULER_IP_ADDRESS, help="Scheduler UDP listen host.")
    parser.add_argument("--scheduler-port", type=int, default=SLOTIS_SCHEDULER_PORT, help="Scheduler UDP listen port.")
    parser.add_argument("--status-host", default=SLOTIS_STATUS_SERVER_IP_ADDRESS, help="Slotis status server host.")
    parser.add_argument("--status-port", type=int, default=SLOTIS_STATUS_SERVER_PORT, help="Slotis status server port.")
    parser.add_argument("--interval", type=float, default=5.0, help="Status update interval in seconds.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    chiller = TCubeChiller(args.serial_port)
    chiller.connect()
    logger.info("Connected to chiller on %s", args.serial_port)

    try:
        chiller.set_setpoint(0.0)
        chiller.run()
        logger.info("Chiller started with setpoint 0.0°C")
    except Exception:
        logger.exception("Failed to initialize chiller on startup")
        chiller.disconnect()
        return

    stop_event = threading.Event()
    status_thread = threading.Thread(
        target=status_stream,
        args=(chiller, args.status_host, args.status_port, args.interval, stop_event),
        daemon=True,
    )
    status_thread.start()

    tcp_thread = threading.Thread(
        target=tcp_temperature_stream,
        args=(chiller, args.status_host, args.status_port, 10.0, stop_event),
        daemon=True,
    )
    tcp_thread.start()

    with ChillerUDPServer((args.scheduler_host, args.scheduler_port), ChillerUDPHandler, chiller) as server:
        logger.info("Listening for scheduler commands on %s:%s", args.scheduler_host, args.scheduler_port)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            logger.info("Stopping chiller client")
        finally:
            stop_event.set()
            status_thread.join(timeout=args.interval + 1.0)
            tcp_thread.join(timeout=11.0)
            try:
                chiller.stop()
                logger.info("Chiller stopped")
            except Exception:
                logger.exception("Error stopping chiller")
            chiller.disconnect()
            logger.info("Disconnected from chiller")


if __name__ == "__main__":
    main()
