from superlotis.drivers.pfeiffer.pfeiffer import Pfeiffer
from superlotis.tools.constants import PFEIFFER_IP_ADDRESS, PFEIFFER_PORT, PFEIFFER_SOCKET_IP_ADDRESS, PFEIFFER_SOCKET_PORT, TEST_STATUS_SERVER_HOST, TEST_STATUS_SERVER_PORT, TEST_SCHEDULER_SERVER_HOST, TEST_SCHEDULER_SERVER_PORT, SLOTIS_SCHEDULER_POLL_INTERVAL, SLOTIS_STATUS_POLL_INTERVAL, SLOTIS_SCHEDULER_IP_ADDRESS, SLOTIS_SCHEDULER_PORT, SLOTIS_STATUS_SERVER_IP_ADDRESS, SLOTIS_STATUS_SERVER_PORT
from superlotis.tools.utilities import DeviceStatusReporter, CommandScheduler, SchedulerPoller, TCPServerThread
import time
import logging
from pathlib import Path

# =========================================================
# CONFIG
# =========================================================

# Identification string of the device for logging
COMPUTER_ID = "LYMAN"
DEVICE_ID = "PFEIFFER"

# Device socket server
DEVICE_SERVER_HOST = PFEIFFER_SOCKET_IP_ADDRESS
DEVICE_SERVER_PORT = PFEIFFER_SOCKET_PORT

# =========================================================
# LOGGING
# =========================================================

LOG_FILE = Path(f"{DEVICE_ID}_client.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

# Suppress INFO messages from the opcua library
logging.getLogger("opcua").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# =========================================================
# PFEIFFER COMMAND PROCESSING
# =========================================================

def process_command(command):

    command = command.strip()

    logger.info("%s: processing '%s'", DEVICE_ID, command)

    # =====================================================
    # start
    # =====================================================

    if command.startswith("start "):

        try:

            pump = str(command.split()[1])

            logger.info(
                "%s: start %s pump",
                DEVICE_ID, pump,
            )
            if pump == 'backing':
                pfeiffer.start_backing()
            if pump == 'turbo':
                pfeiffer.start_turbo()

            return f"start {pump} pump"

        except Exception:
            logger.exception("%s: start pump failed", DEVICE_ID)
            return "error"

    # =====================================================
    # stop
    # =====================================================

    elif command.startswith("stop"):

        try:
    
            pump = str(command.split()[1])
    
            logger.info(
                "%s: stop %s pump",
                DEVICE_ID, pump,
            )
            if pump == 'backing':
                pfeiffer.stop_backing()
            if pump == 'turbo':
                pfeiffer.stop_turbo()
    
            return f"stop {pump} pump"
    
        except Exception:
            logger.exception("%s: stop pump failed", DEVICE_ID)
            return "error"

    # =====================================================
    # get status
    # =====================================================

    elif command.startswith("get status"):

        try:
            status = pfeiffer.get_status()

            logger.info(
                "%s: pfeiffer get status",
                DEVICE_ID
            )

            return f"pfeiffer get status"

        except Exception:
            logger.exception("%s: get status failed", DEVICE_ID)
            return "error"

    elif command.startswith("get backing_temperature"):

        try:
            backing_temperature = pfeiffer.backing.temperature

            logger.info(
                "%s: pfeiffer get backing_temperature = %f",
                DEVICE_ID, backing_temperature
            )

            return f"pfeiffer get backing_temperature = {backing_temperature}"

        except Exception:
            logger.exception("%s: get backing_temperature failed", DEVICE_ID)
            return "error"

    return "unknown command"




# =========================================================
# STATUS SERVER SENDING STATUS OF DEVICE
# =========================================================

class OutletStatusReporter(DeviceStatusReporter):

    """Inherits from generic DeviceStatusReporter class defined in superlotis.tools.utilities"""

    def report_loop(self):
        """
        Continuously report device status information.

        Polls the status of each device, formats the corresponding status
        message, and sends it to the configured UDP endpoint. Any errors
        encountered during status collection or transmission are logged and
        do not terminate the reporting loop.
        """
        while self._running:

            try:
                if self.client is None:
                    self._connect()

                all_status = pfeiffer.get_status()

                for key in all_status:
                    msg = f"set pfeiffer_{key} {all_status[key]}\n"

                    self._send(msg) 

                    self.logger.info(
                        "%s: sent '%s' to %s:%d",
                        self.device_id,
                        msg,
                        self.host,
                        self.port
                    )

                    time.sleep(0.1)

            except Exception:
                self.logger.exception(
                    "%s: pfeiffer status reporting failed",
                    self.device_id
                )

                # Force a reconnect on the next iteration.
                self._close_connection()

            # Wait before sending the next status update cycle.
            time.sleep(self.interval)

# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    # =====================================================
    # CONNECT DEVICE THROUGH DRIVER
    # =====================================================

    pfeiffer = Pfeiffer(ip_address=PFEIFFER_IP_ADDRESS, port=PFEIFFER_PORT)

    logger.info(
        "%s: device connected",
        DEVICE_ID
    )

    # =====================================================
    # START DEVICE SOCKET SERVER THREAD
    # =====================================================

    device_socket_server = TCPServerThread(host=DEVICE_SERVER_HOST, port=DEVICE_SERVER_PORT, logger=logger, process_command=process_command, device_id=DEVICE_ID)
    device_socket_server.start()

    # =====================================================
    # START POLLING FROM SCHEDULER SERVER THREAD
    # =====================================================

    scheduler = CommandScheduler(logger=logger, device_id=DEVICE_ID)
    scheduler_poller = SchedulerPoller(host=SLOTIS_SCHEDULER_IP_ADDRESS, port=SLOTIS_SCHEDULER_PORT, scheduler=scheduler, logger=logger, process_command=process_command, computer_id=COMPUTER_ID, device_id=DEVICE_ID, timeout=5, poll_interval=SLOTIS_SCHEDULER_POLL_INTERVAL)
    scheduler_poller.start_polling_scheduler_server()

    # =====================================================
    # START PUMP STATUS REPORTER THREAD
    # =====================================================

    status_reporter = OutletStatusReporter(host=SLOTIS_STATUS_SERVER_IP_ADDRESS, port=SLOTIS_STATUS_SERVER_PORT, logger=logger, device_id=DEVICE_ID, interval=SLOTIS_STATUS_POLL_INTERVAL)
    status_reporter.start()

    # =====================================================
    # INFINITE LOOP STOPPED BY CTRL+C
    # =====================================================

    while True:
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            device_socket_server.stop()
            scheduler_poller.stop_polling_scheduler_server()
            status_reporter.stop()
            pfeiffer.close()
            del pfeiffer
            break
