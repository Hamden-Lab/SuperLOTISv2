from superlotis.drivers.sophia.sophia import SOPHIA
from superlotis.tools.constants import SOPHIA_SOCKET_IP_ADDRESS, SOPHIA_SOCKET_PORT, SOPHIA_STATUS_KEYS, TEST_STATUS_SERVER_HOST, TEST_STATUS_SERVER_PORT, TEST_SCHEDULER_SERVER_HOST, TEST_SCHEDULER_SERVER_PORT, SLOTIS_SCHEDULER_POLL_INTERVAL, SLOTIS_STATUS_POLL_INTERVAL
from superlotis.tools.utilities import DeviceStatusReporter, CommandScheduler, SchedulerPoller, UDPServerThread
import time
import logging
from pathlib import Path

# =========================================================
# CONFIG
# =========================================================

# Identification string of the device for logging
COMPUTER_ID = "LYMAN"
DEVICE_ID = "SOPHIA"

# Device socket server
DEVICE_SERVER_HOST = SOPHIA_SOCKET_IP_ADDRESS
DEVICE_SERVER_PORT = SOPHIA_SOCKET_PORT

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

logger = logging.getLogger(__name__)

# =========================================================
# SOPHIA COMMAND PROCESSING
# =========================================================

def process_command(command):

    command = command.strip()

    logger.info("%s: processing '%s'", DEVICE_ID, command)

    # reconnect if needed
    if not camera.is_open():
        logger.warning("%s: reconnecting camera", DEVICE_ID)
        camera.open()

    if command.startswith("set exptime"):

        try:
            exptime = float(command.split()[2])

            logger.info(
                "%s: exptime = %s",
                DEVICE_ID, exptime            
            )

            camera.set_exptime(exptime)

            return f"Exposure time set to {exptime} sec"

        except Exception:
            logger.exception("%s: set exptime failed", DEVICE_ID)
            return "error"

    elif command.startswith("set temperature"):

        try:
            temperature = float(command.split()[2])

            logger.info(
                "%s: temperature = %s",
                DEVICE_ID, temperature            
            )

            camera.set_temperature(temperature)

            return f"Temperature set to {temperature} C"

        except Exception:
            logger.exception("%s: set temperature failed", DEVICE_ID)
            return "error"

    elif command.startswith("expose"):

        try:
            data = camera.take_exposure()
            print(data[:10])

            logger.info(
                "%s: exposure started",
                DEVICE_ID            
            )

            size = getattr(data, "nbytes", None)
            if size is None:
                try:
                    size = len(data)
                except Exception:
                    size = "unknown"
            return f"Exposure complete ({size} bytes)"

        except Exception:
            logger.exception("%s: exposure start failed", DEVICE_ID)
            return "error"

    elif command.startswith("get all"):

        try:

            dict_attr = camera.get_all_attributes()

            logger.info(
                "%s: get all attributes = %s",
                DEVICE_ID            
            )

            return dict_attr

        except Exception:
            logger.exception("%s: get all attributes failed", DEVICE_ID)
            return "error"

    elif command.startswith("get exptime"):

        try:
            exptime = camera.get_exptime()

            logger.info(
                "%s: exptime = %f",
                DEVICE_ID,
                exptime,
            )

            return f"Exposure time = {exptime} sec"

        except Exception:
            logger.exception("%s: get exposure time failed", DEVICE_ID)
            return "error"

    elif command.startswith("get temperature"):

        try:
            temperature = camera.get_temperature()

            logger.info(
                "%s: temperature = %f",
                DEVICE_ID,
                temperature,
            )

            return f"Temperature = {temperature} C"

        except Exception:
            logger.exception("%s: get temperature failed", DEVICE_ID)
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

                status_dict = camera.get_all_attributes()

                for key in status_dict:
                    if key in SOPHIA_STATUS_KEYS:

                        msg = f"set SOPHIA_{key} {status_dict[key]}"

                        self.client.sendto(
                            msg.encode("utf-8"),
                            (self.host, self.port)
                        )

                        logger.info(
                            "%s: sent '%s' to %s:%d",
                            self.device_id,
                            msg,
                            self.host,
                            self.port
                        )

            except Exception:
                logger.exception(
                    "%s: outlet status reporting failed",
                    self.device_id
                )

            # Wait before sending the next status update cycle.
            time.sleep(self.interval)

# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    # =====================================================
    # CONNECT DEVICE THROUGH DRIVER
    # =====================================================

    camera = SOPHIA()

    logger.info(
        "%s: device connected",
        DEVICE_ID
    )

    # =====================================================
    # START DEVICE SOCKET SERVER THREAD
    # =====================================================

    device_socket_server = UDPServerThread(host=DEVICE_SERVER_HOST, port=DEVICE_SERVER_PORT, logger=logger, process_command=process_command, device_id=DEVICE_ID)
    device_socket_server.start()

    # =====================================================
    # START POLLING FROM SCHEDULER SERVER THREAD
    # =====================================================

    scheduler = CommandScheduler(logger=logger, device_id=DEVICE_ID)
    scheduler_poller = SchedulerPoller(host=TEST_SCHEDULER_SERVER_HOST, port=TEST_SCHEDULER_SERVER_PORT, scheduler=scheduler, logger=logger, process_command=process_command, computer_id=COMPUTER_ID, device_id=DEVICE_ID, timeout=5, poll_interval=SLOTIS_SCHEDULER_POLL_INTERVAL)
    scheduler_poller.start_polling_scheduler_server()

    # =====================================================
    # START OUTLET STATUS REPORTER THREAD
    # =====================================================

    status_reporter = OutletStatusReporter(host=TEST_STATUS_SERVER_HOST, port=TEST_STATUS_SERVER_PORT, logger=logger, device_id=DEVICE_ID, interval=SLOTIS_STATUS_POLL_INTERVAL)
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
            camera.close()
            del camera
            break
