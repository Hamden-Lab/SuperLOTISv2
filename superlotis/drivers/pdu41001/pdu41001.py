import getpass
import logging
import re
from typing import Any, List, Mapping, Optional, Sequence, Tuple, Union

import keyring
from paramiko import Channel, Transport
from typing_extensions import Self

from superlotis.tools.constants import PDU41001_IP_ADDRESS, PDU41001_PASSWORD, PDU41001_USER

logger = logging.getLogger(__name__)


class PDU41001(object):
    
    KEX_ALGORITHM = "diffie-hellman-group-exchange-sha256"
    KEY_TYPE = "ssh-rsa"
    PROMPT = "CyberPower > "
    DEFAULT_RECV_BUFSIZE = 1024
    LINE_SEPARATOR = "\r\n"
    # CyberPower will disconnect if it receives a keepalive
    KEEPALIVE_INTERVAL = 0
    NUM_OUTLETS = 8

    def __init__(self, host: str, user: str, password: Optional[str] = None):
        self.host = host
        self.user = user
        self.password = (
            password or keyring.get_password(self.host, self.user) or getpass.getpass()
        )

        self.transport: Optional[Transport] = None
        self.channel: Optional[Channel] = None

    def _auth_handler(
        self, title: str, instructions: str, fields: List[Tuple[str, bool]]
    ) -> List[str]:
        return [self.password]

    def __enter__(self) -> Self:
        self.connect()
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def connect(self) -> str:
        """Connect to the PDU and return the received welcome banner."""
        if self.is_open():
            return ""
        t = Transport(self.host)
        o = t.get_security_options()
        o.kex = (self.KEX_ALGORITHM,)
        # o.key_types = (self.KEY_TYPE,)
        t.set_keepalive(self.KEEPALIVE_INTERVAL)

        t.start_client()
        t.auth_interactive(self.user, self._auth_handler)
        self.transport = t
        self.channel = t.open_session()
        self.channel.get_pty()
        self.channel.invoke_shell()
        output = self._recv_until(self.PROMPT).splitlines()
        # return "\n".join(output[:-1])

    def is_open(self) -> bool:
        """True if the connection is open; False otherwise."""
        return bool(self.transport and self.transport.active)

    def close(self) -> None:
        """Close the connection. Do nothing if not open."""
        if self.is_open():
            assert self.transport
            self.transport.close()
        self.transport = None
        self.channel = None

    def _recv_until(self, delim: str, bufsize: int = DEFAULT_RECV_BUFSIZE) -> str:
        assert self.channel
        while True:
            data = self.channel.recv(bufsize).decode()
            if data.endswith(delim):
                return data

    def run(self, cmd: str) -> str:
        """Run a command and return the output.

        Arguments:
            cmd: the command to run

        Returns:
            the output of the command
        """
        assert self.channel
        if cmd != "?" and not cmd.endswith(self.LINE_SEPARATOR):
            cmd += self.LINE_SEPARATOR
        self.channel.sendall(cmd.encode())
        output = self._recv_until(self.PROMPT).splitlines()
        output.pop()
        return "\n".join(output)
    
    def run_as_dict(self, command: str) -> Mapping[str, object]:
        """Run a command and parse its output into a dictionary."""

        response = self.run(command)

        result: dict[str, object] = {}
        current_section: dict[str, str] | None = None
        section_name: str | None = None

        for line in response.splitlines():
            line = line.strip()

            if not line:
                continue

            # Skip separator lines
            if set(line) == {"-"}:
                continue

            # Section header (e.g. "Load", "Utility")
            if ":" not in line:
                section_name = re.sub(r"\s+", "_", line.lower())
                current_section = {}
                result[section_name] = current_section
                continue

            key, value = (part.strip() for part in line.split(":", 1))

            key = re.sub(r"\s+", "_", key.lower())
            value = re.sub(r"\s+", " ", value)

            if current_section is not None:
                current_section[key] = value
            else:
                result[key] = value

        return result

    def get_status(
        self, outlet: Optional[Union[int, str]] = None
    ) -> Sequence[Mapping[str, str]]:
        """Get status of the specified outlet (or all outlets if unspecified).

        Arguments:
            outlet: the name or index of the outlet

        Returns:
            Each item in the sequence is a mapping representing the outlet, with the following keys:

                * index: the index of the outlet (1-8)
                * name: the user-provided name for the outlet
                * status: Off or On
        """
        if outlet:
            status = self.get_status()
            for o in status:
                if o["index"] == str(outlet) or o["name"] == outlet:
                    return [o]
            else:
                raise KeyError(outlet)
        response = self.run("oltsta show")
        status = []
        for line in response.splitlines():
            if m := re.match(
                r"(?P<index>\d)\s+(?P<name>\S+)\s+(?P<status>(Off|On))$", line.strip()
            ):
                status.append(m.groupdict())
        return sorted(status, key=lambda o: o["index"])
    
    def get_power_usage(self) -> Mapping[str, Mapping[str, str]]:
        """Get current power usage statistics."""

        response = self.run("devsta show")

        result: dict[str, dict[str, str]] = {}
        section: str | None = None

        for line in response.splitlines():
            line = line.strip()

            if not line:
                continue

            # Skip separator lines
            if set(line) == {"-"}:
                continue

            # Section header
            if ":" not in line:
                section = line.lower()
                result[section] = {}
                continue

            if section is None:
                continue

            key, value = (part.strip() for part in line.split(":", 1))

            key = re.sub(r"\s+", "_", key.lower())
            value = re.sub(r"\s+", " ", value)

            result[section][key] = value

        return result

    def power_on(self, outlet: Optional[Union[int, str]] = None) -> str:
        """Power on the specified outlet (or all outlets if unspecified).

        Arguments:
            outlet: the name or index of the outlet

        Returns:
            The result of the action
        """
        return self._oltctrl_action("on", outlet)

    def power_off(self, outlet: Optional[Union[int, str]] = None) -> str:
        """Power off the specified outlet (or all outlets if unspecified).

        Arguments:
            outlet: the name or index of the outlet

        Returns:
            The result of the action
        """
        return self._oltctrl_action("off", outlet)

    def reboot(self, outlet: Optional[Union[int, str]] = None) -> str:
        """Reboot the specified outlet (or all outlets if unspecified).

        Arguments:
            outlet: the name or index of the outlet

        Returns:
            The result of the action
        """
        return self._oltctrl_action("reboot", outlet)

    def _oltctrl_action(
        self, action: str, outlet: Optional[Union[int, str]] = None
    ) -> str:
        cmd = "oltctrl index {} act {}"
        if outlet:
            if isinstance(outlet, int) or outlet.isnumeric():
                index = int(outlet)
            else:
                index = int(self.get_status(outlet)[0]["index"])
            return self.run(cmd.format(index, action))
        results = ""
        for i in range(1, self.NUM_OUTLETS + 1):
            results += self.run(cmd.format(i, action))
        return results

if __name__ == "__main__":
    pdu = PDU41001(host=PDU41001_IP_ADDRESS, user=PDU41001_USER, password=PDU41001_PASSWORD)
    pdu.connect()
    pdu.get_status()
