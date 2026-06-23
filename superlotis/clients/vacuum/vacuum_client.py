import argparse
import datetime
import logging
import socket
import sys
import time
from pathlib import Path
from typing import List, Optional, Sequence

from superlotis.drivers.pdu41001.pdu41001 import PDU41001
from superlotis.drivers.pfeiffer.pfeiffer_controller import Controller, Pump
from superlotis.tools.constants import (
    PDU41001_IP_ADDRESS,
    PDU41001_PASSWORD,
    PDU41001_SOCKET_IP_ADDRESS,
    PDU41001_USER,
    SLOTIS_SCHEDULER_IP_ADDRESS,
    SLOTIS_SCHEDULER_PORT,
)

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

SCHEDULER_QUERY = "/all"
INFICON_QUERY_TEMPLATE = "get {gauge} pressure"


def is_float(value: str) -> bool:
    try:
        float(value)
        return True
    except ValueError:
        return False


def parse_schedule_time_token(token: str, fallback: float = 0.0) -> Optional[float]:
    token = token.strip().lower()
    if not token:
        return None
    if token == "now":
        return 0.0
    if token.startswith("+") and is_float(token[1:]):
        return float(token[1:])
    if is_float(token):
        return float(token)
    try:
        datetime.datetime.fromisoformat(token)
        return None
    except ValueError:
        return None


def parse_scheduler_lines(schedule_text: str) -> Sequence[datetime.datetime]:
    now = datetime.datetime.now()
    event_times: List[datetime.datetime] = []

    for line in schedule_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        parts = line.split()
        if not parts:
            continue

        offset: Optional[float] = None
        if parts[0].lower() == "now":
            if len(parts) >= 2 and is_float(parts[1]):
                offset = float(parts[1])
            else:
                offset = 0.0
        elif parts[0].startswith("+") and is_float(parts[0][1:]):
            offset = float(parts[0][1:])
        elif is_float(parts[0]):
            offset = float(parts[0])
        else:
            try:
                event_times.append(datetime.datetime.fromisoformat(parts[0]))
                continue
            except ValueError:
                if len(parts) >= 2 and parts[0].lower() == "now" and is_float(parts[1]):
                    offset = float(parts[1])
                else:
                    continue

        if offset is not None:
            event_times.append(now + datetime.timedelta(seconds=offset))

    return sorted(event_times)


def query_scheduler(host: str, port: int, timeout: float = 2.0) -> Optional[str]:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout)
        try:
            sock.sendto(SCHEDULER_QUERY.encode("utf-8"), (host, port))
            data, _ = sock.recvfrom(4096)
            return data.decode("utf-8", errors="replace")
        except Exception:
            logger.exception("Failed to query scheduler emulator at %s:%s", host, port)
            return None


def query_inficon_pressure(host: str, port: int, gauge: str, timeout: float = 1.0) -> Optional[float]:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout)
        try:
            command = INFICON_QUERY_TEMPLATE.format(gauge=gauge)
            sock.sendto(command.encode("utf-8"), (host, port))
            data, _ = sock.recvfrom(1024)
            value = data.decode("utf-8", errors="replace").strip()
            return float(value)
        except Exception:
            logger.exception("Failed to query Inficon gauge %s at %s:%s", gauge, host, port)
            return None


def get_next_schedule_event(event_times: Sequence[datetime.datetime]) -> Optional[datetime.datetime]:
    now = datetime.datetime.now()
    for event_time in event_times:
        if event_time > now:
            return event_time
    return None


def is_inside_schedule_period(event_times: Sequence[datetime.datetime]) -> bool:
    if len(event_times) < 2:
        return False
    now = datetime.datetime.now()
    return event_times[0] <= now <= event_times[-1]


def start_mvp(mvp: Pump) -> None:
    try:
        if not mvp.pumping_power:
            mvp.pumping_power = True
            logger.info("MVP pump started")
    except Exception:
        logger.exception("Failed to start MVP pump")


def stop_mvp(mvp: Pump) -> None:
    try:
        if mvp.pumping_power:
            mvp.pumping_power = False
            logger.info("MVP pump stopped")
    except Exception:
        logger.exception("Failed to stop MVP pump")


def start_tc80(tc80: Pump) -> None:
    try:
        if not tc80.motor_pump:
            tc80.motor_pump = True
            logger.info("TC80 turbo pump started")
    except Exception:
        logger.exception("Failed to start TC80 turbo pump")


def stop_tc80(tc80: Pump) -> None:
    try:
        if tc80.motor_pump:
            tc80.motor_pump = False
            logger.info("TC80 turbo pump stop requested")
    except Exception:
        logger.exception("Failed to stop TC80 turbo pump")


def wait_for_tc80_stop(tc80: Pump, timeout: float = 300.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if not tc80.motor_pump:
                logger.info("TC80 turbo pump is stopped")
                return
            logger.debug("Waiting for TC80 turbo pump to stop")
        except Exception:
            logger.exception("Error checking TC80 turbo pump stop state")
            return
        time.sleep(1.0)
    logger.warning("Timeout waiting for TC80 turbo pump to stop")


def power_pdu(pdu: PDU41001, outlet: int, on: bool) -> None:
    try:
        if on:
            pdu.power_on(outlet=outlet)
            logger.info("PDU outlet %s turned on", outlet)
        else:
            pdu.power_off(outlet=outlet)
            logger.info("PDU outlet %s turned off", outlet)
    except Exception:
        logger.exception("Failed to %s PDU outlet %s", "turn on" if on else "turn off", outlet)


def shutdown_sequence(
    pdu: PDU41001,
    outlet: int,
    tc80: Pump,
    mvp: Pump,
) -> None:
    logger.info("Starting vacuum shutdown sequence")
    power_pdu(pdu, outlet, on=False)
    stop_tc80(tc80)
    wait_for_tc80_stop(tc80)
    stop_mvp(mvp)
    logger.info("Vacuum shutdown sequence complete")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Vacuum client that polls scheduler emulator and Inficon pressure, then controls MVP, TC80, and PDU outlet.")
    parser.add_argument("--scheduler-host", default=SLOTIS_SCHEDULER_IP_ADDRESS, help="Scheduler emulator host.")
    parser.add_argument("--scheduler-port", type=int, default=SLOTIS_SCHEDULER_PORT, help="Scheduler emulator port.")
    parser.add_argument("--inficon-host", default="127.0.0.1", help="Inficon client UDP host.")
    parser.add_argument("--inficon-port", type=int, default=5150, help="Inficon client UDP port.")
    parser.add_argument("--inficon-gauge", default="PSG550", help="Inficon gauge label to poll for pressure.")
    parser.add_argument("--pdu-outlet", type=int, default=2, help="PDU outlet to switch on/off.")
    parser.add_argument("--pfeiffer-url", default="opc.tcp://127.0.0.1:4840", help="OPC UA URL for the Pfeiffer controller.")
    parser.add_argument("--tc80-on-pressure", type=float, default=0.1, help="Pressure threshold (same units as Inficon) to turn on TC80.")
    parser.add_argument("--pdu-on-pressure", type=float, default=0.01, help="Pressure threshold to turn on the PDU outlet.")
    parser.add_argument("--shutdown-lead-minutes", type=float, default=30.0, help="Minutes before the next schedule event to start shutdown.")
    parser.add_argument("--schedule-poll-interval", type=float, default=10.0, help="Seconds between scheduler emulator polls.")
    parser.add_argument("--pressure-poll-interval", type=float, default=1.0, help="Seconds between Inficon pressure polls.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    try:
        pdu = PDU41001(host=PDU41001_IP_ADDRESS, user=PDU41001_USER, password=PDU41001_PASSWORD)
        pdu.connect()
        logger.info("Connected to PDU at %s", PDU41001_IP_ADDRESS)
    except Exception:
        logger.exception("Failed to connect to PDU")
        return

    controller = Controller(args.pfeiffer_url)
    try:
        controller.client.connect()
        logger.info("Connected to Pfeiffer controller at %s", args.pfeiffer_url)
    except Exception:
        logger.exception("Failed to connect to Pfeiffer controller")
        pdu.close()
        return

    try:
        turbo = Pump(controller, "TC80", 1)
        mvp = Pump(controller, "MVP", 2)
    except Exception:
        logger.exception("Failed to initialize pump objects")
        controller.client.disconnect()
        pdu.close()
        return

    schedule_event_times: List[datetime.datetime] = []
    next_schedule_event: Optional[datetime.datetime] = None
    last_schedule_poll = 0.0
    sequence_started = False
    pdu_powered = False
    turbo_started = False
    mvp_started = False
    shutting_down = False

    def maybe_refresh_schedule() -> None:
        nonlocal schedule_event_times, next_schedule_event, last_schedule_poll
        now_ts = time.time()
        if now_ts - last_schedule_poll < args.schedule_poll_interval:
            return
        last_schedule_poll = now_ts
        schedule_text = query_scheduler(args.scheduler_host, args.scheduler_port)
        if schedule_text is None:
            return
        schedule_event_times = list(parse_scheduler_lines(schedule_text))
        next_schedule_event = get_next_schedule_event(schedule_event_times)
        logger.info(
            "Scheduler poll: %d events, next event in %s",
            len(schedule_event_times),
            f"{(next_schedule_event - datetime.datetime.now()).total_seconds():.1f}s" if next_schedule_event else "none",
        )

    def should_be_outside_period() -> bool:
        if not schedule_event_times:
            return True
        now = datetime.datetime.now()
        if len(schedule_event_times) < 2:
            return now < schedule_event_times[0]
        return now < schedule_event_times[0] or now > schedule_event_times[-1]

    try:
        while True:
            maybe_refresh_schedule()

            pressure = query_inficon_pressure(args.inficon_host, args.inficon_port, args.inficon_gauge)
            if pressure is not None:
                logger.info("Polled %s pressure = %s", args.inficon_gauge, pressure)

            now = datetime.datetime.now()
            if next_schedule_event:
                time_to_next = (next_schedule_event - now).total_seconds()
            else:
                time_to_next = float("inf")

            outside_period = should_be_outside_period()

            if not shutting_down and outside_period and time_to_next > args.shutdown_lead_minutes * 60:
                if not mvp_started:
                    start_mvp(mvp)
                    mvp_started = True
                if mvp_started and not turbo_started and pressure is not None and pressure <= args.tc80_on_pressure:
                    start_tc80(turbo)
                    turbo_started = True
                if turbo_started and not pdu_powered and pressure is not None and pressure <= args.pdu_on_pressure:
                    power_pdu(pdu, args.pdu_outlet, on=True)
                    pdu_powered = True
                if mvp_started or turbo_started or pdu_powered:
                    sequence_started = True

            if sequence_started and time_to_next <= args.shutdown_lead_minutes * 60:
                shutting_down = True
                shutdown_sequence(pdu, args.pdu_outlet, turbo, mvp)
                pdu_powered = False
                turbo_started = False
                mvp_started = False
                sequence_started = False
                shutting_down = False

            time.sleep(args.pressure_poll_interval)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, performing shutdown sequence")
        shutdown_sequence(pdu, args.pdu_outlet, turbo, mvp)
    finally:
        try:
            controller.client.disconnect()
        except Exception:
            logger.exception("Failed to disconnect Pfeiffer controller")
        try:
            pdu.close()
        except Exception:
            logger.exception("Failed to close PDU connection")


if __name__ == "__main__":
    main()
