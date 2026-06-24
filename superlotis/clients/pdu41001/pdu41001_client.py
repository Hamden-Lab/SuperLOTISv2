from superlotis.drivers.pdu41001 import pdu41001
from superlotis.tools.constants import PDU41001_IP_ADDRESS, PDU41001_USER, PDU41001_PASSWORD, PDU41001_SOCKET_IP_ADDRESS, PDU41001_SOCKET_PORT, LYMAN_COMPUTER_IP_ADDRESS, SLOTIS_SCHEDULER_PORT, TEST_STATUS_SERVER_HOST, TEST_STATUS_SERVER_PORT, TEST_SCHEDULER_SERVER_HOST, TEST_SCHEDULER_SERVER_PORT, SLOTIS_SCHEDULER_POLL_INTERVAL
import socket
import socketserver
import threading
import time
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
import re
import datetime
import calendar

# =========================================================
# CONFIG
# =========================================================

# Identification string of the device for logging
DEVICE_ID = "PDU41001"
DEVICE_SYSTEM = "SLOTIS"
DEVICE_SUBSYSTEM = "PDU"

# Device socket server
DEVICE_SERVER_HOST = PDU41001_SOCKET_IP_ADDRESS
DEVICE_SERVER_PORT = PDU41001_SOCKET_PORT

# =========================================================
# LOGGING
# =========================================================

LOG_FILE = Path("pdu41001_client.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

@dataclass
class ParsedCommand:
    raw_line: str
    execute_at: float
    system: str
    subsystem: str
    command: str


# Matches:
# now 0 SLOTIS PDU poweroff 2
NOW_REGEX = re.compile(
    r"""
    ^now
    \s+
    (?P<offset>-?\d+)
    \s+
    (?P<system>\S+)
    \s+
    (?P<subsystem>\S+)
    \s+
    (?P<command>.+)
    $
    """,
    re.VERBOSE,
)


# Matches:
# 0 31 19 18 05 2023 -20 SLOTIS PDU poweroff 2
DATE_REGEX = re.compile(
    r"""
    ^
    (?P<sec>\d+)
    \s+
    (?P<minute>\d+)
    \s+
    (?P<hour>\d+)
    \s+
    (?P<day>\d+)
    \s+
    (?P<month>\d+)
    \s+
    (?P<year>\d+)
    \s+
    (?P<offset>-?\d+)
    \s+
    (?P<system>\S+)
    \s+
    (?P<subsystem>\S+)
    \s+
    (?P<command>.+)
    $
    """,
    re.VERBOSE,
)





def parse_schedule_line(line: str) -> Optional[ParsedCommand]:

    line = line.strip()

    if not line or line.startswith("#"):
        return None

    # =====================================================
    # NOW FORMAT
    # =====================================================

    match = NOW_REGEX.match(line)

    if match:

        system = match.group("system")
        subsystem = match.group("subsystem")

        if (
            system != DEVICE_SYSTEM
            or subsystem != DEVICE_SUBSYSTEM
        ):
            return None

        offset = int(match.group("offset"))

        execute_at = time.time() + offset

        return ParsedCommand(
            raw_line=line,
            execute_at=execute_at,
            system=system,
            subsystem=subsystem,
            command=match.group("command"),
        )

    # =====================================================
    # ABSOLUTE DATETIME FORMAT
    # =====================================================

    match = DATE_REGEX.match(line)

    if match:

        system = match.group("system")
        subsystem = match.group("subsystem")

        if (
            system != DEVICE_SYSTEM
            or subsystem != DEVICE_SUBSYSTEM
        ):
            return None

        sec = int(match.group("sec"))
        minute = int(match.group("minute"))
        hour = int(match.group("hour"))
        day = int(match.group("day"))
        month = int(match.group("month"))
        year = int(match.group("year"))

        offset = int(match.group("offset"))

        dt = datetime.datetime(
            year,
            month,
            day,
            hour,
            minute,
            sec,
        )

        execute_at = calendar.timegm(dt.timetuple()) + offset

        return ParsedCommand(
            raw_line=line,
            execute_at=execute_at,
            system=system,
            subsystem=subsystem,
            command=match.group("command"),
        )

    return None


class CommandScheduler:

    def __init__(self):

        self.scheduled = set()

        self.lock = threading.Lock()

    def schedule(self, parsed: ParsedCommand):

        with self.lock:

            # avoid duplicate scheduling
            if parsed.raw_line in self.scheduled:
                return

            self.scheduled.add(parsed.raw_line)

        thread = threading.Thread(
            target=self._execute_later,
            args=(parsed,),
            daemon=True
        )

        thread.start()

    def _execute_later(self, parsed: ParsedCommand):

        try:

            now = time.time()

            delay = parsed.execute_at - now

            logger.info(
                "%s: command '%s' scheduled in %.2f sec",
                DEVICE_ID,
                parsed.command,
                delay
            )

            # already expired
            if delay < -5:

                logger.warning(
                    "%s: skipping expired command '%s'",
                    DEVICE_ID,
                    parsed.command
                )

                return

            # wait until execution time
            if delay > 0:
                time.sleep(delay)

            logger.info(
                "%s: executing scheduled command '%s'",
                DEVICE_ID,
                parsed.command
            )

            process_command(parsed.command)

        except Exception:

            logger.exception(
                "%s: scheduled execution failed",
                DEVICE_ID
            )

# =========================================================
# PDU COMMAND PROCESSING
# =========================================================

def process_command(command):

    command = command.strip()

    logger.info("%s: processing '%s'", DEVICE_ID, command)

    # reconnect if needed
    if not pdu.is_open():
        logger.warning("%s: reconnecting SSH", DEVICE_ID)
        pdu.connect()

    # =====================================================
    # power on
    # =====================================================

    if command.startswith("poweron "):

        try:
            outlet = int(command.split()[1])

            logger.info(
                "%s: power on outlet %d",
                DEVICE_ID,
                outlet
            )

            pdu.power_on(outlet=outlet)

            return f"outlet {outlet} on"

        except Exception:
            logger.exception("%s: poweron failed", DEVICE_ID)
            return "error"

    # =====================================================
    # power off
    # =====================================================

    elif command.startswith("poweroff "):

        try:
            outlet = int(command.split()[1])

            logger.info(
                "%s: power off outlet %d",
                DEVICE_ID,
                outlet
            )

            pdu.power_off(outlet=outlet)

            return f"outlet {outlet} off"

        except Exception:
            logger.exception("%s: poweroff failed", DEVICE_ID)
            return "error"

    # =====================================================
    # reboot
    # =====================================================

    elif command.startswith("reboot "):

        try:
            outlet = int(command.split()[1])

            logger.info(
                "%s: reboot outlet %d",
                DEVICE_ID,
                outlet
            )

            pdu.reboot(outlet=outlet)

            return f"outlet {outlet} reboot"

        except Exception:
            logger.exception("%s: reboot failed", DEVICE_ID)
            return "error"

    # =====================================================
    # get status
    # =====================================================

    elif command.startswith("get status "):

        try:
            outlet = int(command.split()[2])

            status = pdu.get_status(outlet=outlet)

            logger.info(
                "%s: outlet %d status %s",
                DEVICE_ID,
                outlet,
                status
            )

            return f"outlet {outlet} status {status}"

        except Exception:
            logger.exception("%s: get status failed", DEVICE_ID)
            return "error"

    # =====================================================
    # get powerusage
    # =====================================================

    elif command == "get powerusage":

        try:
            power_usage = pdu.get_power_usage()['load']['device_load']

            logger.info(
                "%s: power usage %s",
                DEVICE_ID,
                power_usage
            )

            return f"power usage {power_usage}"

        except Exception:
            logger.exception("%s: powerusage failed", DEVICE_ID)
            return "error"

    return "unknown command"


# =========================================================
# LOCAL UDP SOCKET SERVER
# =========================================================

class MyUDPHandler(socketserver.BaseRequestHandler):

    def handle(self):

        data = self.request[0].strip()
        sock = self.request[1]

        command = data.decode("utf-8", errors="replace")

        logger.info(
            "%s: received local socket command '%s'",
            DEVICE_ID,
            command
        )

        try:

            result = process_command(command)

            sock.sendto(
                result.encode("utf-8"),
                self.client_address
            )

        except Exception:

            logger.exception("%s: socket request failed", DEVICE_ID)

            sock.sendto(
                b"internal server error",
                self.client_address
            )


class UDPServerThread:

    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.server = socketserver.ThreadingUDPServer(
            (self.host, self.port),
            MyUDPHandler
        )

        self.thread = threading.Thread(
            target=self.server.serve_forever,
            daemon=True
        )

    def start(self):

        logger.info(
            "%s: local UDP server started on %s:%s",
            DEVICE_ID,
            self.host,
            self.port
        )

        self.thread.start()

    def stop(self):

        logger.info("%s: stopping UDP server", DEVICE_ID)

        self.server.shutdown()      # stop serve_forever()
        self.server.server_close()  # close socket
        self.thread.join()          # wait for thread exit

        logger.info("%s: UDP server stopped", DEVICE_ID)

# =========================================================
# SOCKET CLIENT TO POLL SCHEDULER SERVER
# =========================================================

class SchedulerPoller(object):

    def __init__(
    self,
    host,
    port,
    scheduler,
    timeout=5,
    poll_interval=SLOTIS_SCHEDULER_POLL_INTERVAL
):

        logger.info(
            "%s: starting master polling thread",
            DEVICE_ID
        )
        self.scheduler = scheduler
        self.host = host
        self.port = port
        self.client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.client.settimeout(self.timeout)

    def start_polling_scheduler_server(self):
        self._polling_scheduler_server = True
        self.poll_scheduler_server_thread = threading.Thread(target=self.poll_scheduler)
        self.poll_scheduler_server_thread.start()
        logger.info(
            "%s: START SCHEDULER SERVER POLLING THREAD",
            DEVICE_ID
        )

    def stop_polling_scheduler_server(self):
        self._polling_scheduler_server = False
        self.poll_scheduler_server_thread.join()
        logger.info(
            "%s: STOP SCHEDULER SERVER POLLING THREAD",
            DEVICE_ID
        )

    def poll_scheduler(self):

        while self._polling_scheduler_server:

            try:

                # request all commands
                self.client.sendto(b"/all", (self.host, self.port))

                # receive response
                response, _ = self.client.recvfrom(8192)

                decoded = response.decode("utf-8")

                logger.info(
                    "%s: received master data:\n%s",
                    DEVICE_ID,
                    decoded
                )

                # process line by line
                lines = decoded.strip().splitlines()

                for line in lines:

                    parsed = parse_schedule_line(line)

                    if parsed is None:
                        continue

                    logger.info(
                        "%s: accepted command '%s'",
                        DEVICE_ID,
                        parsed.command
                    )

                    self.scheduler.schedule(parsed)

            except Exception:
                logger.exception(
                    "%s: polling failed",
                    DEVICE_ID
                )

            time.sleep(self.poll_interval)

# =========================================================
# 
# =========================================================


class OutletStatusReporter:

    def __init__(self, host, port, interval=10):
        self.host = host
        self.port = port
        self.interval = interval
        self.client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def start(self):
        self._running = True
        self.thread = threading.Thread(
            target=self.report_loop,
            daemon=True
        )
        self.thread.start()

        logger.info(
            "%s: START OUTLET STATUS REPORTER THREAD",
            DEVICE_ID
        )

    def stop(self):
        self._running = False
        self.thread.join()

        logger.info(
            "%s: STOP OUTLET STATUS REPORTER THREAD",
            DEVICE_ID
        )

    def report_loop(self):

        while self._running:

            try:

                for outlet in range(1, 9):

                    status = pdu.get_status(outlet=outlet)

                    msg = f"set pdu_outlet_{outlet:d} {status}"

                    self.client.sendto(
                        msg.encode("utf-8"),
                        (self.host, self.port)
                    )

                    logger.info(
                        "%s: sent '%s'",
                        DEVICE_ID,
                        msg
                    )

            except Exception:
                logger.exception(
                    "%s: outlet status reporting failed",
                    DEVICE_ID
                )

            time.sleep(self.interval)

# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    # =====================================================
    # CONNECT DEVICE THROUGH DRIVER
    # =====================================================

    pdu = pdu41001.PDU41001(host=PDU41001_IP_ADDRESS, user=PDU41001_USER, password=PDU41001_PASSWORD)
    pdu.connect()

    logger.info(
        "%s: device connected",
        DEVICE_ID
    )

    # =====================================================
    # START DEVICE SOCKET SERVER THREAD
    # =====================================================

    device_socket_server = UDPServerThread(host=DEVICE_SERVER_HOST, port=DEVICE_SERVER_PORT)
    device_socket_server.start()

    # =====================================================
    # START POLLING FROM SCHEDULER SERVER THREAD
    # =====================================================

    # scheduler_poller = SchedulerPoller(host=TEST_SCHEDULER_SERVER_HOST, port=TEST_SCHEDULER_SERVER_PORT)
    # scheduler_poller.start_polling_scheduler_server()

    scheduler = CommandScheduler()


    scheduler_poller = SchedulerPoller(host=TEST_SCHEDULER_SERVER_HOST, port=TEST_SCHEDULER_SERVER_PORT, scheduler=scheduler)
    scheduler_poller.start_polling_scheduler_server()

    # =====================================================
    # START OUTLET STATUS REPORTER THREAD
    # =====================================================

    status_reporter = OutletStatusReporter(host=TEST_STATUS_SERVER_HOST, port=TEST_STATUS_SERVER_PORT, interval=10)
    status_reporter.start()


    while True:
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            device_socket_server.stop()
            scheduler_poller.stop_polling_scheduler_server()
            status_reporter.stop()
            pdu.close()
            del pdu
            break
