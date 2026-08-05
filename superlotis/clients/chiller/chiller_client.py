from serial.tools import list_ports
from superlotis.drivers.chiller.chiller import TCubeChiller
from superlotis.tools.constants import CHILLER_SERIAL_NUMBER, CHILLER_SOCKET_IP_ADDRESS, CHILLER_SOCKET_PORT, CHILLER_SERIAL_BAUDRATE, TEST_STATUS_SERVER_HOST, TEST_STATUS_SERVER_PORT, TEST_SCHEDULER_SERVER_HOST, TEST_SCHEDULER_SERVER_PORT, SLOTIS_SCHEDULER_POLL_INTERVAL, SLOTIS_STATUS_POLL_INTERVAL
from superlotis.tools.utilities import DeviceStatusReporter, CommandScheduler, SchedulerPoller, UDPServerThread
import time
import logging
from pathlib import Path

# =========================================================
# CONFIG
# =========================================================

# Identification string of the device for logging
COMPUTER_ID = "LYMAN"
DEVICE_ID = "CHILLER"

# Device socket server
DEVICE_SERVER_HOST = CHILLER_SOCKET_IP_ADDRESS
DEVICE_SERVER_PORT = CHILLER_SOCKET_PORT

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
# CHILLER COMMAND PROCESSING
# =========================================================

def process_command(command):

    command = command.strip()

    logger.info("%s: processing '%s'", DEVICE_ID, command)

    # reconnect if needed
    if not chiller.is_open():
        logger.warning("%s: reconnecting serial interface", DEVICE_ID)
        chiller.connect()

    # =====================================================
    # power on
    # =====================================================

    if command.startswith("start"):

        try:
            chiller.start()

            logger.info(
                "%s: start chiller",
                DEVICE_ID,
            )

            return f"chiller started"

        except Exception:
            logger.exception("%s: start chiller failed", DEVICE_ID)
            return "error"

    # =====================================================
    # power off
    # =====================================================

    elif command.startswith("stop"):

        try:
            chiller.stop()

            logger.info(
                "%s: stop chiller",
                DEVICE_ID,
            )

            return f"chiller stopped"

        except Exception:
            logger.exception("%s: stop chiller failed", DEVICE_ID)
            return "error"

    # =====================================================
    # get run state
    # =====================================================

    elif command.startswith("get run_state"):

        try:
            run_state = chiller.get_run_state()

            logger.info(
                "%s: chiller run_state = %s",
                DEVICE_ID, run_state
            )

            return f"chiller runstate = {run_state}"

        except Exception:
            logger.exception("%s: chiller read runstate failed", DEVICE_ID)
            return "error"

    # =====================================================
    # get pwm
    # =====================================================

    elif command.startswith("get pwm"):

        try:
            pwm = chiller.get_pwm()

            logger.info(
                "%s: chiller pwm = %s",
                DEVICE_ID, pwm
            )

            return f"chiller pwm = {pwm}"

        except Exception:
            logger.exception("%s: chiller read pwm failed", DEVICE_ID)
            return "error"
        
    # =====================================================
    # get status
    # =====================================================

    elif command.startswith("get status"):

        try:
            status = chiller.get_status()

            logger.info(
                "%s: chiller status = %s",
                DEVICE_ID, status
            )

            return f"chiller status = {status}"

        except Exception:
            logger.exception("%s: chiller read status failed", DEVICE_ID)
            return "error"

    # =====================================================
    # get faults
    # =====================================================

    elif command.startswith("get faults"):

        try:
            faults = chiller.get_faults()

            logger.info(
                "%s: chiller faults = %s",
                DEVICE_ID, faults
            )

            return f"chiller faults = {faults}"

        except Exception:
            logger.exception("%s: chiller read faults failed", DEVICE_ID)
            return "error"

    # =====================================================
    # get all
    # =====================================================

    elif command.startswith("get all"):

        try:
            all_status = chiller.get_all()

            logger.info(
                "%s: chiller all status",
                DEVICE_ID
            )

            return f"chiller all status"

        except Exception:
            logger.exception("%s: chiller read all status failed", DEVICE_ID)
            return "error"
        
    # =====================================================
    # get temperature
    # =====================================================

    elif command.startswith("get temperature"):

        try:
            temperature = chiller.get_temperature()

            logger.info(
                "%s: chiller temperature = %f",
                DEVICE_ID, temperature
            )

            return f"chiller temperature = {temperature}"

        except Exception:
            logger.exception("%s: chiller read temperature failed", DEVICE_ID)
            return "error"

    # =====================================================
    # get pump temperature
    # =====================================================

    elif command.startswith("get pump_temperature"):

        try:
            temperature = chiller.get_pump_temperature()

            logger.info(
                "%s: chiller pump temperature = %f",
                DEVICE_ID, temperature
            )

            return f"chiller pump temperature = {temperature}"

        except Exception:
            logger.exception("%s: chiller read pump temperature failed", DEVICE_ID)
            return "error"

    # =====================================================
    # get setpoint
    # =====================================================

    elif command.startswith("get setpoint"):

        try:
            setpoint = chiller.get_setpoint()

            logger.info(
                "%s: chiller setpoint = %f",
                DEVICE_ID, setpoint
            )

            return f"chiller setpoint = {setpoint}"

        except Exception:
            logger.exception("%s: chiller read setpoint failed", DEVICE_ID)
            return "error"


    # =====================================================
    # set setpoint
    # =====================================================

    elif command.startswith("set setpoint "):

        try:
            setpoint = float(command.split()[2])

            chiller.set_setpoint(setpoint)

            logger.info(
                "%s: set chiller setpoint = %f",
                DEVICE_ID, setpoint
            )

            return f"set chiller setpoint = {setpoint}"

        except Exception:
            logger.exception("%s: chiller set setpoint failed", DEVICE_ID)
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
                all_status = chiller.get_all()
                for key in all_status:
                    msg = f"set chiller_{key} {all_status[key]}"

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
                    "%s: chiller status reporting failed",
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

    for port in list_ports.comports():
        if port.serial_number == CHILLER_SERIAL_NUMBER:
            chiller = TCubeChiller(port.device, baudrate=CHILLER_SERIAL_BAUDRATE)
            chiller.connect()

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
            chiller.disconnect()
            del chiller
            break
