import datetime
import logging
import socketserver
import threading
from typing import List

from superlotis.drivers.sophia.sophia import SOPHIA
from superlotis.tools.constants import SLOTIS_SCHEDULER_IP_ADDRESS, SLOTIS_SCHEDULER_PORT

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


if __name__ == "__main__":
    camera = SOPHIA()
    logger.info("Initialized SOPHIA camera")
    with SophiaUDPServer((HOST, PORT), SophiaUDPHandler, camera) as server:
        logger.info("Listening for scheduler commands on %s:%s", HOST, PORT)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            logger.info("Stopping Sophia scheduler listener")
