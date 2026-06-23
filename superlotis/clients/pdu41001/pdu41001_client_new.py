from superlotis.drivers.pdu41001 import pdu41001
from superlotis.tools.constants import PDU41001_IP_ADDRESS, PDU41001_USER, PDU41001_PASSWORD, PDU41001_SOCKET_IP_ADDRESS, PDU41001_SOCKET_PORT, LYMAN_COMPUTER_IP_ADDRESS, SLOTIS_SCHEDULER_PORT
import socket
import socketserver
import threading
import time
import logging
from pathlib import Path

# =========================================================
# CONFIG
# =========================================================

# Identification string of the device for logging
DEVICE_ID = "PDU41001"

# Device socket server
DEVICE_SERVER_HOST = PDU41001_SOCKET_IP_ADDRESS
DEVICE_SERVER_PORT = PDU41001_SOCKET_PORT

# Scheduler socket server
SCHEDULER_SERVER_HOST = LYMAN_COMPUTER_IP_ADDRESS
SCHEDULER_SERVER_PORT = SLOTIS_SCHEDULER_PORT

# Scheduler poll interval
SCHEDULER_POLL_INTERVAL = 5

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

    def __init__(self, timeout=5, poll_interval=SCHEDULER_POLL_INTERVAL):
        logger.info(
            "%s: starting master polling thread",
            DEVICE_ID
        )

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
                self.client.sendto(b"/all", (SCHEDULER_SERVER_HOST, SCHEDULER_SERVER_PORT))

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

                    line = line.strip()

                    if not line:
                        continue

                    logger.info(
                        "%s: parsing line '%s'",
                        DEVICE_ID,
                        line
                    )

                    # Example:
                    # now 0 SLOTIS PDU poweroff 2

                    parts = line.split()

                    if len(parts) < 5:
                        continue

                    # extract actual command
                    # poweroff 2
                    cmd = " ".join(parts[4:])

                    process_command(cmd)

            except Exception:
                logger.exception(
                    "%s: polling failed",
                    DEVICE_ID
                )

            time.sleep(self.poll_interval)



# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    # =====================================================
    # CONNECT DEVICE
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

    device_socket_server = UDPServerThread(DEVICE_SERVER_HOST, DEVICE_SERVER_PORT)
    device_socket_server.start()

    # later when user wants to stop:
    # socket_server.stop()

    # =====================================================
    # START POLLING FROM SCHEDULER SERVER THREAD
    # =====================================================

    scheduler_poller = SchedulerPoller()
    scheduler_poller.start_polling_scheduler_server()

    # later when user wants to stop:
    # scheduler_poller.stop_polling_scheduler_server()