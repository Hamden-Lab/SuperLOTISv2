import datetime
import logging
import socket
import socketserver
import threading
import time
from typing import List

from superlotis.drivers.sophia.sophia import SOPHIA
from superlotis.tools.constants import (
    SLOTIS_SCHEDULER_IP_ADDRESS,
    SLOTIS_SCHEDULER_PORT,
    SLOTIS_STATUS_SERVER_IP_ADDRESS,
    SLOTIS_STATUS_SERVER_PORT,
    PDU41001_SOCKET_IP_ADDRESS,
    PDU41001_SOCKET_PORT,
    SOPHIA_OUTLET,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

HOST = SLOTIS_SCHEDULER_IP_ADDRESS
PORT = SLOTIS_SCHEDULER_PORT  # Port to listen on (non-privileged ports are > 1023)


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


def execute_camera_command(camera: SOPHIA, command_tokens: List[str]) -> str:
    if not command_tokens:
        return "No command provided"

    cmd = command_tokens[0].lower()
    if cmd == "get":
        if len(command_tokens) < 2:
            return "Missing get parameter"

        param = command_tokens[1].lower()
        if param == "exptime":
            return str(camera.get_exptime())
        if param == "temperature":
            return str(camera.get_temperature())
        if param == "all_attributes":
            return str(camera.get_all_attributes())
        return f"Unknown get parameter: {param}"

    if cmd == "set":
        if len(command_tokens) < 3:
            return "Missing set parameter or value"

        param = command_tokens[1].lower()
        value = command_tokens[2]
        if param == "exptime":
            camera.set_exptime(int(value))
            return "Exposure time set"
        if param == "temperature":
            camera.set_temperature(float(value))
            return "Temperature set"
        return f"Unknown set parameter: {param}"

    if cmd == "expose":
        data = camera.take_exposure()
        size = getattr(data, "nbytes", None)
        if size is None:
            try:
                size = len(data)
            except Exception:
                size = "unknown"
        return f"Exposure complete ({size} bytes)"

    return f"Unknown command: {cmd}"


def schedule_command(camera: SOPHIA, line: str) -> str:
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
        result = execute_camera_command(camera, command_tokens)
        logger.info("Executed immediately: %s => %s", line, result)
        return f"EXECUTED: {result}"

    def task() -> None:
        result = execute_camera_command(camera, command_tokens)
        logger.info("Scheduled command executed after %.1f sec: %s => %s", delay, line, result)

    timer = threading.Timer(delay, task)
    timer.daemon = True
    timer.start()
    return f"SCHEDULED in {delay:.1f}s: {line}"


def process_scheduler_payload(payload: bytes, camera: SOPHIA) -> bytes:
    message = payload.decode("utf-8", errors="replace")
    lines = [line for line in message.splitlines() if line.strip()]
    if not lines:
        return b"No scheduler commands received"

    responses = []
    for line in lines:
        response = schedule_command(camera, line)
        responses.append(response)
    return "\n".join(responses).encode("utf-8")


class SophiaUDPHandler(socketserver.BaseRequestHandler):
    def handle(self):
        data = self.request[0].strip()
    
        udp_socket = self.request[1]
        logger.info("Scheduler request from %s: %s", self.client_address, data.decode("utf-8", errors="replace"))
        response = process_scheduler_payload(data, self.server.camera)
        udp_socket.sendto(response, self.client_address)


class SophiaUDPServer(socketserver.ThreadingUDPServer):
    allow_reuse_address = True

    def __init__(self, server_address, handler_class, camera: SOPHIA):
        super().__init__(server_address, handler_class)
        self.camera = camera


def _counter_loop(counter: dict, lock: threading.Lock, stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        with lock:
            counter["value"] += 1
        stop_event.wait(1.0)


def _query_pdu_outlet_status(outlet: int, timeout: float = 1.0) -> str:
    """Query the local PDU client via UDP for outlet status. Returns 'on'/'off' or 'unknown'."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(timeout)
            cmd = f"get status {outlet}".encode("utf-8")
            s.sendto(cmd, (PDU41001_SOCKET_IP_ADDRESS, PDU41001_SOCKET_PORT))
            data, _ = s.recvfrom(1024)
            resp = data.decode("utf-8", errors="replace").strip()
            # expected: 'outlet {n} status {state}'
            parts = resp.split()
            if len(parts) >= 4 and parts[-2] == "status":
                return parts[-1]
            # fallback: return last token
            if parts:
                return parts[-1]
    except Exception:
        logger.exception("Failed to query PDU outlet status")
    return "unknown"


def tcp_status_stream(camera: SOPHIA, status_host: str, status_port: int, counter: dict, lock: threading.Lock, stop_event: threading.Event, interval: float = 1.0) -> None:
    """Send camera status lines over TCP every `interval` seconds to the status server.

    Lines sent:
      set sophia_camera_status {on/off}
      set SOPHIA_ccdtemp {T}
      set SOPHIA_exposure {t}
      set sophia_exposing {yes/no}
      set sophia_count {x}
    """
    logger.info("Starting Sophia TCP status stream to %s:%s every %.1f seconds", status_host, status_port, interval)
    sock = None
    while not stop_event.is_set():
        try:
            if sock is None:
                sock = socket.create_connection((status_host, status_port), timeout=5)

            # camera power via PDU
            pdu_state = _query_pdu_outlet_status(SOPHIA_OUTLET)
            camera_power = pdu_state if pdu_state in ("on", "off") else ("on" if pdu_state.lower().startswith("on") else "off")

            # camera metrics
            try:
                temp = camera.get_temperature()
            except Exception:
                logger.exception("Failed to read camera temperature")
                temp = None

            try:
                exptime = camera.get_exptime()
            except Exception:
                logger.exception("Failed to read exposure time")
                exptime = None

            try:
                status = camera.get_status()
            except Exception:
                logger.exception("Failed to read camera status")
                status = None

            exposing = "no"
            if status is not None:
                s = str(status).lower()
                if s and ("expos" in s or "running" in s or "busy" in s):
                    exposing = "yes"

            with lock:
                count = counter.get("value", 0)

            lines = []
            lines.append(f"set sophia_camera_status {camera_power}")
            if temp is not None:
                try:
                    lines.append(f"set SOPHIA_ccdtemp {float(temp):.1f}")
                except Exception:
                    lines.append(f"set SOPHIA_ccdtemp {temp}")
            else:
                lines.append("set SOPHIA_ccdtemp unknown")

            lines.append(f"set SOPHIA_exposure {exptime}")
            lines.append(f"set sophia_exposing {exposing}")
            lines.append(f"set sophia_count {count}")

            try:
                for line in lines:
                    sock.sendall(line.encode("utf-8") + b"\n")
                    time.sleep(0.1)  # Small delay to avoid overwhelming the server
                logger.debug("Sent Sophia TCP status to %s:%s", status_host, status_port)
            except Exception:
                logger.exception("Failed to send Sophia status over TCP, will reconnect")
                try:
                    sock.close()
                except Exception:
                    pass
                sock = None

        except Exception:
            logger.exception("TCP connection error for Sophia status stream")
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


if __name__ == "__main__":
    camera = SOPHIA()
    logger.info("Initialized SOPHIA camera")

    stop_event = threading.Event()
    counter = {"value": 0}
    counter_lock = threading.Lock()

    counter_thread = threading.Thread(target=_counter_loop, args=(counter, counter_lock, stop_event), daemon=True)
    counter_thread.start()

    tcp_thread = threading.Thread(
        target=tcp_status_stream,
        args=(camera, SLOTIS_STATUS_SERVER_IP_ADDRESS, SLOTIS_STATUS_SERVER_PORT, counter, counter_lock, stop_event, 1.0),
        daemon=True,
    )
    tcp_thread.start()

    with SophiaUDPServer((HOST, PORT), SophiaUDPHandler, camera) as server:
        logger.info("Listening for scheduler commands on %s:%s", HOST, PORT)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            logger.info("Stopping Sophia scheduler listener")
        finally:
            stop_event.set()
            counter_thread.join(timeout=2.0)
            tcp_thread.join(timeout=2.0)
