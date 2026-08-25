import re
from dataclasses import dataclass
import time
import datetime
import calendar
from typing import Optional
import threading
import socketserver
from functools import partial
import socket
from typing import Any, Callable
from email.message import EmailMessage
import smtplib
import ssl

from superlotis.tools.constants import ALERT_EMAIL_ADDRESS, GOOGLE_APP_PASSWORD, ALERT_EMAIL_BODY_BASE, ALERT_EMAIL_SUBJECT_BASE, ALERT_EMAIL_RCV

# =========================================================
# PARSING SCHEDULER COMMAND LINES
# =========================================================

@dataclass
class ParsedCommand:
    raw_line: str
    execute_at: float
    computer_id: str
    device_id: str
    command: str

# Matches:
# now 0 SLOTIS PDU poweroff 2
NOW_REGEX = re.compile(
    r"""
    ^now
    \s+
    (?P<offset>-?\d+)
    \s+
    (?P<computer_id>\S+)
    \s+
    (?P<device_id>\S+)
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
    (?P<computer_id>\S+)
    \s+
    (?P<device_id>\S+)
    \s+
    (?P<command>.+)
    $
    """,
    re.VERBOSE,
)

# Matches:
# 1756155300 SLOTIS PDU poweroff 2
UNIX_REGEX = re.compile(
    r"""
    ^
    (?P<timestamp>\d+)
    \s+
    (?P<computer_id>\S+)
    \s+
    (?P<device_id>\S+)
    \s+
    (?P<command>.+)
    $
    """,
    re.VERBOSE,
)

def parse_schedule_line(line: str, computer_id: str, device_id: str) -> Optional[ParsedCommand]:

    line = line.strip()

    if not line or line.startswith("#"):
        return None

    # =====================================================
    # NOW FORMAT
    # =====================================================

    match = NOW_REGEX.match(line)

    if match:

        parsed_computer_id = match.group("computer_id")
        parsed_device_id = match.group("device_id")

        if (
            parsed_computer_id != computer_id
            or parsed_device_id != device_id
        ):
            return None

        offset = int(match.group("offset"))

        execute_at = time.time() + offset

        return ParsedCommand(
            raw_line=line,
            execute_at=execute_at,
            computer_id=parsed_computer_id,
            device_id=parsed_device_id,
            command=match.group("command"),
        )

    # =====================================================
    # ABSOLUTE DATETIME FORMAT
    # =====================================================

    match = DATE_REGEX.match(line)

    if match:

        parsed_computer_id = match.group("computer_id")
        parsed_device_id = match.group("device_id")

        if (
            parsed_computer_id != computer_id
            or parsed_device_id != device_id
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
            computer_id=computer_id,
            device_id=device_id,
            command=match.group("command"),
        )

    # =====================================================
    # UNIX TIMESTAMP FORMAT
    # =====================================================

    match = UNIX_REGEX.match(line)

    if match:
        parsed_computer_id = match.group("computer_id")
        parsed_device_id = match.group("device_id")

        if (
            parsed_computer_id != computer_id
            or parsed_device_id != device_id
        ):
            return None

        timestamp = int(match.group("timestamp"))
        # offset = int(match.group("offset"))

        execute_at = timestamp #+ offset

        return ParsedCommand(
            raw_line=line,
            execute_at=execute_at,
            computer_id=parsed_computer_id,
            device_id=parsed_device_id,
            command=match.group("command"),
        )

    return None

def send_email_alert(system, error_message):
    msg = EmailMessage()
    msg.set_content(ALERT_EMAIL_BODY_BASE + error_message)
    msg['Subject'] = ALERT_EMAIL_SUBJECT_BASE + system
    msg['From'] = ALERT_EMAIL_ADDRESS
    msg['To'] = ALERT_EMAIL_RCV
    context = ssl.create_default_context()
    try:
        # Connect to Gmail's secure SMTP server
        # TODO : setup App Password in Google Account
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(ALERT_EMAIL_ADDRESS, GOOGLE_APP_PASSWORD)
            server.send_message(msg)
            print("Email alert sent successfully!")
    except Exception as e:
        print(f"Failed to send email: {e}")


# =========================================================
# LOCAL UDP SOCKET SERVER HANDLER
# =========================================================
class MyTCPHandler(socketserver.BaseRequestHandler):
    """
    Handle incoming TCP socket requests.

    Receives a command from a TCP client, processes it, and returns the
    command result to the client. Any processing errors are logged and
    result in a generic error response.
    """

    def __init__(self, *args, logger, process_command, **kwargs):
        """
        Initialize the request handler.

        Args:
            logger: Logger instance used for request and error logging.
            process_command: Function used to process received commands.
        """
        self.logger = logger
        self.process_command = process_command
        super().__init__(*args, **kwargs)

    def handle(self):
        """
        Process commands received over the TCP connection.

        TCP is a byte stream, so the connection is read until the client
        closes it. Commands are expected to be newline-delimited.
        """
        try:
            data = self.request.recv(8192)

            if not data:
                return

            command = data.decode(
                "utf-8",
                errors="replace"
            ).strip()

            self.logger.info(
                "received local socket command '%s'",
                command
            )

            result = self.process_command(command)

            self.request.sendall(
                result.encode("utf-8")
            )

        except Exception:
            self.logger.exception(
                "socket request failed"
            )

            try:
                self.request.sendall(
                    b"internal server error"
                )
            except Exception:
                self.logger.exception(
                    "failed to send error response"
                )



# class MyUDPHandler(socketserver.BaseRequestHandler):
#     """
#     Handle incoming UDP socket requests.

#     Receives a command from a UDP client, processes it, and returns the
#     command result to the sender. Any processing errors are logged and
#     result in a generic error response.
#     """

#     def __init__(self, *args, logger, process_command, **kwargs):
#         """
#         Initialize the request handler.

#         Args:
#             logger: Logger instance used for request and error logging.
#         """
#         self.logger = logger
#         self.process_command = process_command
#         super().__init__(*args, **kwargs)

#     def handle(self):
#         """
#         Process a single UDP request.

#         The incoming datagram is decoded as UTF-8, passed to the command
#         processor, and the resulting response is sent back to the client.
#         If command processing fails, an error message is returned instead.
#         """
#         data = self.request[0].strip()
#         sock = self.request[1]

#         command = data.decode("utf-8", errors="replace")

#         self.logger.info(
#             "received local socket command '%s'",
#             command
#         )

#         try:
#             result = self.process_command(command)

#             sock.sendto(
#                 result.encode("utf-8"),
#                 self.client_address
#             )

#         except Exception:
#             self.logger.exception(
#                 "socket request failed"
#             )

#             sock.sendto(
#                 b"internal server error",
#                 self.client_address
#             )


# =========================================================
# LOCAL UDP SOCKET SERVER THREAD
# =========================================================

class TCPServerThread:
    """
    Run a TCP server in a dedicated background thread.

    This class manages the lifecycle of a
    ``socketserver.ThreadingTCPServer`` instance, providing methods to
    start and stop the server cleanly.
    """

    def __init__(self, host, port, logger, process_command, device_id):
        """
        Initialize the TCP server and its worker thread.

        Args:
            host: Host address to bind the server to.
            port: TCP port to listen on.
            logger: Logger instance.
            process_command: Function used to process commands.
            device_id: Identifier for the device.
        """
        self.host = host
        self.port = port
        self.logger = logger
        self.device_id = device_id

        self.handler_class = partial(
            MyTCPHandler,
            logger=logger,
            process_command=process_command
        )

        self.server = socketserver.ThreadingTCPServer(
            (self.host, self.port),
            self.handler_class
        )

        self.thread = threading.Thread(
            target=self.server.serve_forever,
            daemon=True
        )

    def start(self):
        """
        Start the TCP server in a background thread.
        """
        self.logger.warning(
            "%s: local TCP server started on %s:%s",
            self.device_id,
            self.host,
            self.port
        )

        self.thread.start()

    def stop(self):
        """
        Stop the TCP server and wait for the worker thread to exit.
        """
        self.logger.warning(
            "%s: stopping TCP server",
            self.device_id
        )

        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

        self.logger.warning(
            "%s: TCP server stopped",
            self.device_id
        )



# class UDPServerThread:
#     """
#     Run a UDP server in a dedicated background thread.

#     This class manages the lifecycle of a
#     ``socketserver.ThreadingUDPServer`` instance, providing methods to
#     start and stop the server cleanly.
#     """

#     def __init__(self, host, port, logger, process_command, device_id):
#         """
#         Initialize the UDP server and its worker thread.

#         Args:
#             host: Host address to bind the server to.
#             port: UDP port to listen on.
#         """
#         self.host = host
#         self.port = port
#         self.logger = logger
#         self.device_id = device_id

#         self.handler_class = partial(
#             MyUDPHandler,
#             logger=logger, process_command=process_command
#         )

#         self.server = socketserver.ThreadingUDPServer(
#             (self.host, self.port),
#             self.handler_class
#         )

#         self.thread = threading.Thread(
#             target=self.server.serve_forever,
#             daemon=True
#         )

#     def start(self):
#         """
#         Start the UDP server in a background thread.

#         Logs the server endpoint and begins processing incoming UDP
#         requests.
#         """
#         self.logger.warning(
#             "%s: local UDP server started on %s:%s",
#             self.device_id,
#             self.host,
#             self.port
#         )

#         self.thread.start()

#     def stop(self):
#         """
#         Stop the UDP server and wait for the worker thread to exit.

#         Shuts down the server loop, closes the underlying socket, and
#         blocks until the server thread has terminated.
#         """
#         self.logger.warning(
#             "%s: stopping UDP server",
#             self.device_id
#         )

#         # Stop the server loop accepting new requests.
#         self.server.shutdown()

#         # Release the bound UDP socket.
#         self.server.server_close()

#         # Wait for the server thread to terminate.
#         self.thread.join()

#         self.logger.warning(
#             "%s: UDP server stopped",
#             self.device_id
#         )


# =========================================================
# SOCKET CLIENT TO POLL SCHEDULER SERVER
# =========================================================

class SchedulerPoller(object):
    """
    Poll a remote scheduler server for scheduled commands.

    This class periodically requests command schedules from a master
    scheduler over TCP, parses the returned schedule entries, and submits
    accepted commands to a local ``CommandScheduler`` instance.
    """

    def __init__(
        self,
        host,
        port,
        scheduler,
        logger,
        process_command: Callable[[], Any],
        computer_id,
        device_id,
        timeout=5,
        poll_interval=5
    ):
        """
        Initialize the scheduler poller.

        Args:
            host: Hostname or IP address of the scheduler server.
            port: TCP port of the scheduler server.
            scheduler: Local scheduler used to queue accepted commands.
            timeout: Socket timeout in seconds.
            poll_interval: Delay between polling attempts in seconds.
        """
        self.host = host
        self.port = port
        self.scheduler = scheduler
        self.logger = logger
        self.process_command = process_command
        self.computer_id = computer_id
        self.device_id = device_id

        self.timeout = timeout
        self.poll_interval = poll_interval

        self._polling_scheduler_server = False
        self.poll_scheduler_server_thread = None

        self.logger.warning(
            "%s: starting master polling thread",
            self.device_id
        )

    def start_polling_scheduler_server(self):
        """
        Start the scheduler polling thread.
        """
        self._polling_scheduler_server = True

        self.poll_scheduler_server_thread = threading.Thread(
            target=self.poll_scheduler,
            daemon=True
        )

        self.poll_scheduler_server_thread.start()

        self.logger.warning(
            "%s: START SCHEDULER SERVER POLLING THREAD",
            self.device_id
        )

    def stop_polling_scheduler_server(self):
        """
        Stop the scheduler polling thread.
        """
        self._polling_scheduler_server = False

        if self.poll_scheduler_server_thread is not None:
            self.poll_scheduler_server_thread.join()

        self.logger.warning(
            "%s: STOP SCHEDULER SERVER POLLING THREAD",
            self.device_id
        )

    def poll_scheduler(self):
        """
        Continuously poll the remote scheduler server.

        Each polling cycle establishes a TCP connection, requests the
        current schedule, receives the response, and closes the connection.
        """

        while self._polling_scheduler_server:

            client = None

            try:
                # Create a new TCP connection for this polling cycle.
                client = socket.socket(
                    socket.AF_INET,
                    socket.SOCK_STREAM
                )

                client.settimeout(self.timeout)

                client.connect(
                    (self.host, self.port)
                )

                # Request all scheduled commands from the master server.
                client.sendall(
                    b"all\n"
                )

                # Receive the scheduler response payload.
                response = client.recv(2*8192)


                # # NOTE: dangerous chatgpt edit
                # chunks = []

                # while True:
                #     chunk = client.recv(8192)

                #     if not chunk:
                #         break

                #     chunks.append(chunk)

                # response = b"".join(chunks)

                # # End of it

                if not response:
                    raise ConnectionError(
                        "scheduler server closed the connection"
                    )

                decoded = response.decode("utf-8")

                # Process each returned schedule entry.
                lines = decoded.strip().splitlines()

                for line in lines:

                    self.logger.info(
                        "%s: received : %s",
                        self.device_id, line
                    )

                    parsed = parse_schedule_line(
                        line=line,
                        computer_id=self.computer_id,
                        device_id=self.device_id
                    )

                    # Ignore lines that do not apply to this device.
                    if parsed is None:
                        continue

                    self.scheduler.schedule(
                        parsed,
                        self.process_command
                    )

            except Exception:
                self.logger.exception(
                    "%s: polling failed",
                    self.device_id
                )

            finally:
                if client is not None:
                    try:
                        client.close()
                    except Exception:
                        self.logger.exception(
                            "%s: failed to close scheduler TCP connection",
                            self.device_id
                        )

            # Wait before the next polling cycle.
            time.sleep(self.poll_interval)


# class SchedulerPoller(object):
#     """
#     Poll a remote scheduler server for scheduled commands.

#     This class periodically requests command schedules from a master
#     scheduler over UDP, parses the returned schedule entries, and submits
#     accepted commands to a local ``CommandScheduler`` instance.
#     """

#     def __init__(
#         self,
#         host,
#         port,
#         scheduler,
#         logger,
#         process_command: Callable[[], Any], #function
#         computer_id,
#         device_id,
#         timeout=5,
#         poll_interval=5
#     ):
#         """
#         Initialize the scheduler poller.

#         Args:
#             host: Hostname or IP address of the scheduler server.
#             port: UDP port of the scheduler server.
#             scheduler: Local scheduler used to queue accepted commands.
#             timeout: Socket timeout in seconds.
#             poll_interval: Delay between polling attempts in seconds.
#         """
#         self.host = host
#         self.port = port
#         self.scheduler = scheduler
#         self.logger = logger
#         self.process_command = process_command
#         self.computer_id = computer_id
#         self.device_id = device_id
    
#         self.client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
#         self.timeout = timeout
#         self.poll_interval = poll_interval

#         self.logger.warning(
#             "%s: starting master polling thread",
#             self.device_id
#         )

#         self.client.settimeout(self.timeout)

#     def start_polling_scheduler_server(self):
#         """
#         Start the scheduler polling thread.

#         The polling thread periodically contacts the remote scheduler
#         server and processes any returned schedule entries.
#         """
#         self._polling_scheduler_server = True

#         self.poll_scheduler_server_thread = threading.Thread(
#             target=self.poll_scheduler
#         )

#         self.poll_scheduler_server_thread.start()

#         self.logger.warning(
#             "%s: START SCHEDULER SERVER POLLING THREAD",
#             self.device_id
#         )

#     def stop_polling_scheduler_server(self):
#         """
#         Stop the scheduler polling thread.

#         Signals the polling loop to exit and waits for the polling thread
#         to terminate.
#         """
#         self._polling_scheduler_server = False

#         self.poll_scheduler_server_thread.join()

#         self.logger.warning(
#             "%s: STOP SCHEDULER SERVER POLLING THREAD",
#             self.device_id
#         )

#     def poll_scheduler(self):
#         """
#         Continuously poll the remote scheduler server.

#         Requests the current schedule, parses each returned schedule line,
#         and submits valid commands to the configured scheduler. Any polling
#         or parsing errors are logged and do not terminate the polling loop.
#         """
#         while self._polling_scheduler_server:

#             try:
#                 # Request all scheduled commands from the master server.
#                 self.client.sendto(
#                     b"/all",
#                     (self.host, self.port)
#                 )

#                 # Receive the scheduler response payload.
#                 response, _ = self.client.recvfrom(8192)

#                 decoded = response.decode("utf-8")

#                 # self.logger.info(
#                 #     "%s: received master data:\n%s",
#                 #     self.device_id,
#                 #     decoded
#                 # )

#                 # Process each returned schedule entry.
#                 lines = decoded.strip().splitlines()

#                 for line in lines:

#                     parsed = parse_schedule_line(
#                         line=line,
#                         computer_id=self.computer_id,
#                         device_id=self.device_id
#                     )

#                     # Ignore lines that do not apply to this device.
#                     if parsed is None:
#                         continue

#                     self.scheduler.schedule(parsed, self.process_command)

#             except Exception:
#                 self.logger.exception(
#                     "%s: polling failed",
#                     self.device_id
#                 )

#             # Wait before the next polling cycle.
#             time.sleep(self.poll_interval)


# =========================================================
# COMMAND SCHEDULER FOR SPECIFIC TIME
# =========================================================

class CommandScheduler:
    """
    Schedule commands for execution at a specified future time.

    This class prevents duplicate scheduling of the same raw command line
    and executes commands asynchronously using daemon threads.
    """

    def __init__(self, logger, device_id):
        """
        Initialize the command scheduler.

        Attributes:
            scheduled (set[str]): Tracks raw command lines that have already
                been scheduled to prevent duplicate execution.
            lock (threading.Lock): Synchronizes access to the scheduled set.
        """
        self.logger = logger
        self.device_id = device_id
        self.scheduled = set()
        self.lock = threading.Lock()

    def schedule(self, parsed: ParsedCommand, process_command: Callable[[], Any]): #function
        """
        Schedule a parsed command for future execution.

        If the command's raw input line has already been scheduled, the
        request is ignored.

        Args:
            parsed: Parsed command containing execution timing and command
                information.
        """
        with self.lock:

            # Avoid scheduling the same command more than once.
            if parsed.raw_line in self.scheduled:
                return

            self.scheduled.add(parsed.raw_line)

            self.logger.info(
                    "%s: accepted command '%s'",
                    self.device_id,
                    parsed.command
            )

        thread = threading.Thread(
            target=self._execute_later,
            args=(parsed, process_command),
            daemon=True
        )

        thread.start()

    def _execute_later(self, parsed: ParsedCommand, process_command: Callable[[], Any]): #function
        """
        Execute a command at its scheduled time.

        Commands that are significantly past their scheduled execution time
        are skipped. Any execution errors are logged and suppressed so they
        do not terminate the scheduler thread.

        Args:
            parsed: Parsed command containing the execution timestamp and
                command text.
        """
        try:
            now = time.time()
            delay = parsed.execute_at - now

            self.logger.info(
                "%s: command '%s' scheduled in %.2f sec",
                self.device_id,
                parsed.command,
                delay
            )

            # Skip commands that have been expired for more than 5 seconds.
            if delay < -5:
                self.logger.warning(
                    "%s: skipping expired command '%s'",
                    self.device_id,
                    parsed.command
                )
                return

            # Wait until the scheduled execution time.
            if delay > 0:
                time.sleep(delay)

            self.logger.info(
                "%s: executing scheduled command '%s'",
                self.device_id,
                parsed.command
            )

            process_command(parsed.command)

        except Exception:
            self.logger.exception(
                "%s: scheduled execution failed",
                self.device_id
            )


# =========================================================
# DEVICE STATUS REPORTER TO SEND TO STATUS SERVER
# =========================================================

class DeviceStatusReporter:
    """
    Periodically report device status information to a remote server.

    This class runs a background thread that queries device status from the
    local PDU and sends status updates to a remote UDP endpoint at regular
    intervals.
    """

    def __init__(self, host, port, logger, device_id, interval=10):
        """
        Initialize the device status reporter.

        Args:
            host: Hostname or IP address of the remote UDP receiver.
            port: UDP port of the remote receiver.
            interval: Reporting interval in seconds.
        """
        self.host = host
        self.port = port
        self.device_id = device_id
        self.logger = logger
        self.interval = interval
        # self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self.client = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM
        )

        self._running = False
        self.thread = None

    def start(self):
        """
        Start the device status reporting thread.
        """
        self._running = True

        self.thread = threading.Thread(
            target=self.report_loop,
            daemon=True
        )

        self.thread.start()

        self.logger.warning(
            "%s: START DEVICE STATUS REPORTER THREAD",
            self.device_id
        )

    def stop(self):
        """
        Stop the device status reporting thread.
        """
        self._running = False

        if self.thread is not None:
            self.thread.join()

        self._close_connection()

        self.logger.warning(
            "%s: STOP DEVICE STATUS REPORTER THREAD",
            self.device_id
        )

    def _connect(self):
        """
        Connect to the remote TCP endpoint.
        """
        if self.client is None:
            self.client = socket.socket(
                socket.AF_INET,
                socket.SOCK_STREAM
            )

        self.client.connect((self.host, self.port))

        self.logger.info(
            "%s: connected to %s:%d",
            self.device_id,
            self.host,
            self.port
        )

    def _close_connection(self):
        """
        Close the TCP connection.
        """
        if self.client is not None:
            try:
                self.client.close()
            except Exception:
                self.logger.exception(
                    "%s: failed to close TCP connection",
                    self.device_id
                )
            finally:
                self.client = None

    def _send(self, msg):
        """
        Send a message over the TCP connection.
        """
        try:
            if self.client is None:
                self._connect()

            self.client.sendall(msg.encode("utf-8"))

        except (ConnectionError, OSError):
            self.logger.exception(
                "%s: TCP send failed",
                self.device_id
            )

            # The connection may no longer be usable.
            self._close_connection()

            raise