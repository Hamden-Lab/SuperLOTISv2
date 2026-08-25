from superlotis.drivers.sophia.sophia import SOPHIA
from superlotis.tools.constants import SOPHIA_IMAGE_BASE_NAME, SOPHIA_IMAGE_DIR, SOPHIA_IMAGE_EXTENSION, SOPHIA_SOCKET_IP_ADDRESS, SOPHIA_SOCKET_PORT, SOPHIA_STATUS_KEYS, TEST_STATUS_SERVER_HOST, TEST_STATUS_SERVER_PORT, TEST_SCHEDULER_SERVER_HOST, TEST_SCHEDULER_SERVER_PORT, SLOTIS_SCHEDULER_POLL_INTERVAL, SLOTIS_STATUS_POLL_INTERVAL, SLOTIS_SCHEDULER_IP_ADDRESS, SLOTIS_SCHEDULER_PORT, SLOTIS_STATUS_SERVER_IP_ADDRESS, SLOTIS_STATUS_SERVER_PORT
from superlotis.tools.utilities import DeviceStatusReporter, CommandScheduler, SchedulerPoller, TCPServerThread
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
            hdr = camera.header_populator()
            data = camera.take_exposure()
            # print(data[:10])

            logger.info(
                "%s: exposure started",
                DEVICE_ID            
            )
            filename = camera.save_image(data, header=hdr, output_dir=SOPHIA_IMAGE_DIR, base_name=SOPHIA_IMAGE_BASE_NAME, extension=SOPHIA_IMAGE_EXTENSION)
            size = getattr(data, "nbytes", None)
            if size is None:
                try:
                    size = len(data)
                except Exception:
                    size = "unknown"
            return f"Exposure complete ({size} bytes), saved to {filename}"

            
            

        except Exception:
            logger.exception("%s: exposure start failed", DEVICE_ID)
            return "error"

    elif command.startswith("take bias"):
    
            try:
                hdr = camera.header_populator()
                data = camera.take_bias()
                # print(data[:10])
    
                logger.info(
                    "%s: exposure started",
                    DEVICE_ID            
                )
                filename = camera.save_image(data, header=hdr, output_dir=SOPHIA_IMAGE_DIR, base_name=f"BIAS_{SOPHIA_IMAGE_BASE_NAME}", extension=SOPHIA_IMAGE_EXTENSION)
                size = getattr(data, "nbytes", None)
                if size is None:
                    try:
                        size = len(data)
                    except Exception:
                        size = "unknown"
                return f"Bias complete ({size} bytes), saved to {filename}"
    
                
                
    
            except Exception:
                logger.exception("%s: exposure start failed", DEVICE_ID)
                return "error"

    elif command.startswith("take dark"):
    
            try:
                hdr = camera.header_populator()
                data = camera.take_dark()
                # print(data[:10])
    
                logger.info(
                    "%s: exposure started",
                    DEVICE_ID            
                )
                filename = camera.save_image(data, header=hdr, output_dir=SOPHIA_IMAGE_DIR, base_name=f"DARK_{SOPHIA_IMAGE_BASE_NAME}", extension=SOPHIA_IMAGE_EXTENSION)
                size = getattr(data, "nbytes", None)
                if size is None:
                    try:
                        size = len(data)
                    except Exception:
                        size = "unknown"
                return f"Exposure complete ({size} bytes), saved to {filename}"
    
                
                
    
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

    """Reports outlet status information over TCP."""

    def report_loop(self):
        """
        Continuously report device status information.
        """

        while self._running:

            try:
                if self.client is None:
                    self._connect()

                status_dict = camera.get_all_attributes()

                for key in status_dict:
                    if key in SOPHIA_STATUS_KEYS:
                        normalized_key = key.lower().replace(" ", "_")
                        msg = f"set SOPHIA_{normalized_key} {status_dict[key]}\n"

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
                    "%s: outlet status reporting failed",
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

    camera = SOPHIA()

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
    # START OUTLET STATUS REPORTER THREAD
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
            camera.close()
            del camera
            break
