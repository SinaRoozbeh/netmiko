"""Mellanox MLNX-OS Switch support."""
from typing import Optional
import re
from netmiko.cisco_base_connection import CiscoSSHConnection
from netmiko import log


class MellanoxMlnxosSSH(CiscoSSHConnection):
    """Mellanox MLNX-OS Switch support."""

    def enable(
        self, cmd: str = "enable", pattern: str = "#", re_flags: int = re.IGNORECASE
    ) -> str:
        """Enter into enable mode."""
        output = ""
        if not self.check_enable_mode():
            self.write_channel(self.normalize_cmd(cmd))
            output += self.read_until_prompt_or_pattern(
                pattern=pattern, re_flags=re_flags
            )
            if not self.check_enable_mode():
                raise ValueError("Failed to enter enable mode.")
        return output

    def config_mode(
        self, config_command: str = "config term", pattern: str = "#", re_flags: int = 0
    ) -> str:
        return super().config_mode(config_command=config_command, pattern=pattern)

    def check_config_mode(
        self, check_string: str = "(config", pattern: str = r"#"
    ) -> bool:
        return super().check_config_mode(check_string=check_string, pattern=pattern)

    def disable_paging(
        self,
        command: str = "no cli session paging enable",
        delay_factor: float = 1.0,
        cmd_verify: bool = True,
        pattern: Optional[str] = None,
    ) -> str:
        return super().disable_paging(
            command=command,
            delay_factor=delay_factor,
            cmd_verify=cmd_verify,
            pattern=pattern,
        )

    def exit_config_mode(self, exit_config: str = "exit", pattern: str = "#") -> str:
        """Mellanox does not support a single command to completely exit configuration mode.

        Consequently, need to keep checking and sending "exit".
        """
        output = ""
        check_count = 12
        while check_count >= 0:
            if self.check_config_mode():
                self.write_channel(self.normalize_cmd(exit_config))
                output += self.read_until_pattern(pattern=pattern)
            else:
                break
            check_count -= 1

        # One last check for whether we successfully exited config mode
        if self.check_config_mode():
            raise ValueError("Failed to exit configuration mode")

        log.debug(f"exit_config_mode: {output}")
        return output

    def save_config(
        self,
        cmd: str = "configuration write",
        confirm: bool = False,
        confirm_response: str = "",
    ) -> str:
        """Save Config on Mellanox devices Enters and Leaves Config Mode"""
        output = self.enable()
        output += self.config_mode()
        output += self.send_command(cmd)
        output += self.exit_config_mode()
        return output
