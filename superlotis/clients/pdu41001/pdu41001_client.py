from superlotis.drivers.pdu41001 import pdu41001
from superlotis.tools.constants import PDU41001_IP_ADDRESS, PDU41001_USER, PDU41001_PASSWORD, PDU41001_SOCKET_IP_ADDRESS, PDU41001_SOCKET_PORT
import socketserver
import logging
from pathlib import Path

# To identify whate device is replying on the socket
DEVICE_ID = "PDU41001"
# Socket server parameters
HOST = PDU41001_SOCKET_IP_ADDRESS
PORT = PDU41001_SOCKET_PORT

# Log file path
LOG_FILE = Path("pdu41001_client.log")
# Logging parameters
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()  # also keep output in terminal
    ]
)
logger = logging.getLogger(__name__)


def process_command(command):

    command = command.decode("utf-8").strip()

    # The socket is closed for the PDU side every 10 minutes.
    # Need to check and reopen manually.
    if pdu.is_open() == False:
        pdu.connect()

    # power on <outlet>
    if command.startswith("power on "):
        try:
            outlet = int(command.split()[2])
            logger.info("%s: power on outlet %d", DEVICE_ID, outlet)
            pdu.power_on(outlet=outlet)
            return f"outlet {outlet} on".encode("utf-8")
        except (IndexError, ValueError):
            logger.warning("%s: Invalid outlet number in '%s'", DEVICE_ID, command)
            return f"Invalid outlet number".encode("utf-8")
        
    # power off <outlet>
    elif command.startswith("power off "):
        try:
            outlet = int(command.split()[2])
            logger.info("%s: power off outlet %d", DEVICE_ID, outlet)
            pdu.power_off(outlet=outlet)
            return f"outlet {outlet} off".encode("utf-8")
        except (IndexError, ValueError):
            logger.warning("%s: Invalid outlet number in '%s'", DEVICE_ID, command)
            return f"Invalid outlet number".encode("utf-8")
        
    # reboot <outlet>
    elif command.startswith("reboot "):
        try:
            outlet = int(command.split()[2])
            logger.info("%s: reboot outlet %d", DEVICE_ID, outlet)
            pdu.reboot(outlet=outlet)
            return f"outlet {outlet} reboot".encode("utf-8")
        except (IndexError, ValueError):
            logger.warning("%s: Invalid outlet number in '%s'", DEVICE_ID, command)
            return f"Invalid outlet number".encode("utf-8")

    # get status
    elif command.startswith("get status "):
        try:
            outlet = int(command.split()[2])
            logger.info("%s: get status outlet %d", DEVICE_ID, outlet)
            status = pdu.get_status(outlet=outlet)
            return f"outlet {outlet} status {status}".encode("utf-8")
        except (IndexError, ValueError):
            logger.warning("%s: Invalid outlet number in '%s'", DEVICE_ID, command)
            return f"Invalid outlet number".encode("utf-8")

    # get power usage
    elif command == "get powerusage":
        try:
            outlet = int(command.split()[2])
            logger.info("%s: get powerusage", DEVICE_ID)
            power_usage = pdu.get_power_usage()['load']['device_load']
            return f"power usage {power_usage}".encode("utf-8")
        except (IndexError, ValueError):
            logger.warning("%s: Invalid outlet number in '%s'", DEVICE_ID, command)
            return f"Invalid outlet number".encode("utf-8")

    return b"Unknown command"
    

class MyUDPHandler(socketserver.BaseRequestHandler):

    def handle(self):
        data = self.request[0].strip()
        socket = self.request[1]

        logger.info(
            "%s: %s sent: %s",
            DEVICE_ID,
            self.client_address[0],
            data.decode("utf-8", errors="replace")
        )

        try:
            res = process_command(data)

            logger.info(
                "%s: response: %s",
                DEVICE_ID,
                res.decode("utf-8", errors="replace")
            )

            socket.sendto(res, self.client_address)

        except Exception:
            logger.exception("%s: error processing request", DEVICE_ID)
            socket.sendto(
                f"{DEVICE_ID}: Internal server error".encode("utf-8"),
                self.client_address
            )

if __name__ == "__main__":

    pdu = pdu41001.PDU41001(
        host=PDU41001_IP_ADDRESS,
        user=PDU41001_USER,
        password=PDU41001_PASSWORD
    )

    pdu.connect()
    logger.info("%s: SSH connection established", DEVICE_ID)

    with socketserver.UDPServer((HOST, PORT), MyUDPHandler) as server:
        try:
            logger.info("%s: START SOCKET SERVER", DEVICE_ID)
            server.serve_forever()

        except KeyboardInterrupt:
            logger.info("%s: STOP SOCKET SERVER", DEVICE_ID)

        finally:
            pdu.close()
            logger.info("%s: STOP SSH CONNECTION", DEVICE_ID)