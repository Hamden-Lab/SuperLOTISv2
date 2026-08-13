from superlotis.drivers.pdu41001 import pdu41001
from superlotis.tools.constants import PDU41001_IP_ADDRESS, PDU41001_USER, PDU41001_PASSWORD, PDU41001_SOCKET_IP_ADDRESS, PDU41001_SOCKET_PORT, PDU41001_NUMBER_OUTLETS, TEST_STATUS_SERVER_HOST, TEST_STATUS_SERVER_PORT, TEST_SCHEDULER_SERVER_HOST, TEST_SCHEDULER_SERVER_PORT, SLOTIS_SCHEDULER_POLL_INTERVAL, SLOTIS_STATUS_POLL_INTERVAL, ALERT_INTERVAL_SECONDS
from superlotis.tools.utilities import DeviceStatusReporter, CommandScheduler, SchedulerPoller, UDPServerThread, send_email_alert
import time
import logging
from pathlib import Path

# =========================================================
# CONFIG
# =========================================================

# Identification string of the device for logging
COMPUTER_ID = "LYMAN"
DEVICE_ID = "PDU"

# Device socket server
DEVICE_SERVER_HOST = PDU41001_SOCKET_IP_ADDRESS
DEVICE_SERVER_PORT = PDU41001_SOCKET_PORT

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
# PDU COMMAND PROCESSING
# =========================================================

def process_command(command):

    command = command.strip()

    logger.info("%s: processing '%s'", DEVICE_ID, command)

    # reconnect if needed
    if not pdu.is_open():
        logger.warning("%s: reconnecting SSH", DEVICE_ID)
        pdu.connect()
        logger.info("Connected")

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

        # KS: required to avoid crash when starting client...
        time.sleep(5)

        while self._running:

            try:
                # Report the current state of each managed outlet.
                for outlet in range(1, PDU41001_NUMBER_OUTLETS+1):

                    status = pdu.get_status(
                        outlet=outlet
                    )[0]["status"].lower()

                    msg = f"set pdu_outlet_{outlet:d} {status}"

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

                power_usage = pdu.get_power_usage()
                # Get the power in Watt
                power = float(power_usage['load']['device_load'].split('/')[1].replace('W', '').replace(' ', ''))

                msg = f"set pdu_power {power}"
                
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

                consecutive_failures = 0
                last_email_alert_time = time.time()

            except Exception:
                logger.exception(
                    "%s: outlet status reporting failed",
                    self.device_id
                )

                try:
                    if pdu.is_open():
                        logger.info("Closing connection...")
                        pdu.close()
                        logger.info("Connection closed.")
                except Exception:
                    logger.info("Attempting reconnect...")
                    pdu.connect()
                    logger.info("Reconnect successful.")

                try:
                    logger.info("Attempting reconnect...")
                    pdu.connect()
                    logger.info("Reconnect successful.")
                    break
                except Exception:
                    logger.exception("Reconnect failed.")
                    time.sleep(5)
                
                consecutive_failures += 1
                
                if consecutive_failures >= 5:
                    current_time = time.time()
                
                    if consecutive_failures == 5 or (current_time - last_email_alert_time) >= ALERT_INTERVAL_SECONDS:
                        send_email_alert(DEVICE_ID, f"Reporting failed {consecutive_failures} times in a row. Check the device connection.")
                        last_email_alert_time = current_time

            # Wait before sending the next status update cycle.
            time.sleep(self.interval)

# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    # =====================================================
    # CONNECT DEVICE THROUGH DRIVER
    # =====================================================

    pdu = pdu41001.PDU41001(host=PDU41001_IP_ADDRESS, user=PDU41001_USER, password=PDU41001_PASSWORD)
    logger.info("Connecting PDU...")
    pdu.connect()
    logger.info("Connected")

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
            logger.info("Closing PDU...")
            pdu.close()
            logger.info("Closed")
            del pdu
            break
