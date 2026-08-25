from serial.tools import list_ports
from superlotis.drivers.inficon.inficon import PxG55xRS485
from superlotis.tools.constants import ALERT_INTERVAL_SECONDS, INFICON_SOCKET_IP_ADDRESS, INFICON_SOCKET_PORT, PSG550_SERIAL_NUMBER, PCG550_SERIAL_NUMBER, TEST_STATUS_SERVER_HOST, TEST_STATUS_SERVER_PORT, TEST_SCHEDULER_SERVER_HOST, TEST_SCHEDULER_SERVER_PORT, SLOTIS_SCHEDULER_POLL_INTERVAL, SLOTIS_STATUS_POLL_INTERVAL, SLOTIS_SCHEDULER_IP_ADDRESS, SLOTIS_SCHEDULER_PORT, SLOTIS_STATUS_SERVER_IP_ADDRESS, SLOTIS_STATUS_SERVER_PORT
from superlotis.tools.utilities import DeviceStatusReporter, CommandScheduler, SchedulerPoller, TCPServerThread, send_email_alert
import time
import logging
from pathlib import Path

# =========================================================
# CONFIG
# =========================================================

# Identification string of the device for logging
COMPUTER_ID = "LYMAN"
DEVICE_ID = "INFICON"

# Device socket server
DEVICE_SERVER_HOST = INFICON_SOCKET_IP_ADDRESS
DEVICE_SERVER_PORT = INFICON_SOCKET_PORT

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
# INFICON COMMAND PROCESSING
# =========================================================

def process_command(command):

    command = command.strip()

    logger.info("%s: processing '%s'", DEVICE_ID, command)

    # reconnect if needed
    if not camera_gauge.is_open():
        logger.warning("%s: reconnecting serial interface of camera gauge", DEVICE_ID)
        camera_gauge.connect()

        # reconnect if needed
    if not pump_gauge.is_open():
        logger.warning("%s: reconnecting serial interface of pump gauge", DEVICE_ID)
        pump_gauge.connect()

    # =====================================================
    # get pressure
    # =====================================================

    if command.startswith("get pump_pressure"):

        try:
            pressure = pump_gauge.get_pressure_real()

            logger.info(
                "%s: pump pressure = %f",
                DEVICE_ID,
                pressure
            )

            return f"pump pressure = {pressure:.3e}"

        except Exception:
            logger.exception("%s: can't read pump pressure", DEVICE_ID)
            return "error"

    elif command.startswith("get camera_pressure"):

        try:
            pressure = camera_gauge.get_pressure_real()

            logger.info(
                "%s: camera pressure = %f",
                DEVICE_ID,
                pressure
            )

            return f"camera pressure = {pressure:.3e}"

        except Exception:
            logger.exception("%s: can't read camera pressure", DEVICE_ID)
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

        consecutive_failures = 0
        last_email_alert_time = time.time()

        while self._running:

            try:

                if self.client is None:
                    self._connect()

                camera_pressure = camera_gauge.get_pressure_real()
                pump_pressure = pump_gauge.get_pressure_real()

                msg = f"set camera_pressure {camera_pressure:.3e}\n"

                self._send(msg)

                self.logger.info(
                    "%s: sent '%s' to %s:%d",
                    self.device_id,
                    msg,
                    self.host,
                    self.port
                )

                time.sleep(0.1)

                msg = f"set pump_pressure {pump_pressure:.3e}\n"

                self._send(msg)

                self.logger.info(
                    "%s: sent '%s' to %s:%d",
                    self.device_id,
                    msg,
                    self.host,
                    self.port
                )

                consecutive_failures = 0
                last_email_alert_time = time.time()

            except Exception:

                logger.exception(
                    "%s: outlet status reporting failed",
                    self.device_id
                )

                # Force a reconnect on the next iteration.
                self._close_connection()

                # try:
                #     pump_gauge.disconnect()
                #     camera_gauge.disconnect()

                #     pump_gauge.connect()
                #     camera_gauge.connect()
                # except Exception:
                #     logger.exceptio n(
                #         "%s: Attempting to reconnect",
                #         self.device_id
                #  )

                # consecutive_failures += 1

                # if consecutive_failures >= 5:
                #     current_time = time.time()

                #     if consecutive_failures == 5 or (current_time - last_email_alert_time) >= ALERT_INTERVAL_SECONDS:
                #         send_email_alert(DEVICE_ID, f"Reporting failed {consecutive_failures} times in a row. Check the device connection.")
                #         last_email_alert_time = current_time

            # Wait before sending the next status update cycle.
            time.sleep(self.interval)

# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    # =====================================================
    # CONNECT DEVICE THROUGH DRIVER
    # =====================================================

    for port in list_ports.comports():
        if port.serial_number == PSG550_SERIAL_NUMBER:
            pump_gauge = PxG55xRS485(port=port.device)
            pump_gauge.connect()
        if port.serial_number == PCG550_SERIAL_NUMBER:
            camera_gauge = PxG55xRS485(port=port.device)
            camera_gauge.connect()

    logger.info(
        "%s: devices connected",
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
    # START GAUGE STATUS REPORTER THREAD
    # =====================================================

    # status_reporter = OutletStatusReporter(host=TEST_STATUS_SERVER_HOST, port=TEST_STATUS_SERVER_PORT, logger=logger, device_id=DEVICE_ID, interval=SLOTIS_STATUS_POLL_INTERVAL)
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
            camera_gauge.close()
            pump_gauge.close()
            del camera_gauge
            del pump_gauge
            break
