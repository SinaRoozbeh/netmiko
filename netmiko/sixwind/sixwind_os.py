from typing import Any
import time
from netmiko.cisco_base_connection import CiscoBaseConnection


class SixwindOSBase(CiscoBaseConnection):
    def session_preparation(self) -> None:
        """Prepare the session after the connection has been established."""
        self.ansi_escape_codes = True
        self._test_channel_read()
        self.set_base_prompt()
        # Clear the read buffer
        time.sleep(0.3 * self.global_delay_factor)
        self.clear_buffer()

    def disable_paging(self, *args: Any, **kwargs: Any) -> str:
        """6WIND requires no-pager at the end of command, not implemented at this time."""
        return ""

    def set_base_prompt(
        self,
        pri_prompt_terminator: str = ">",
        alt_prompt_terminator: str = "#",
        delay_factor: float = 1.0,
    ) -> str:
        """Sets self.base_prompt: used as delimiter for stripping of trailing prompt in output."""

        prompt = super().set_base_prompt(
            pri_prompt_terminator=pri_prompt_terminator,
            alt_prompt_terminator=alt_prompt_terminator,
            delay_factor=delay_factor,
        )
        prompt = prompt.strip()
        self.base_prompt = prompt
        return self.base_prompt

    def config_mode(
        self, config_command: str = "edit running", pattern: str = "", re_flags: int = 0
    ) -> str:
        """Enter configuration mode."""

        return super().config_mode(
            config_command=config_command, pattern=pattern, re_flags=re_flags
        )

    def commit(self, comment: str = "", delay_factor: float = 1.0) -> str:
        """
        Commit the candidate configuration.

        Raise an error and return the failure if the commit fails.
        """

        delay_factor = self.select_delay_factor(delay_factor)
        error_marker = "Failed to generate committed config"
        command_string = "commit"

        output = self.config_mode()
        output += self.send_command(
            command_string,
            strip_prompt=False,
            strip_command=False,
            delay_factor=delay_factor,
            expect_string=r"#",
        )
        output += self.exit_config_mode()

        if error_marker in output:
            raise ValueError(f"Commit failed with following errors:\n\n{output}")

        return output

    def exit_config_mode(self, exit_config: str = "exit", pattern: str = r">") -> str:
        """Exit configuration mode."""

        return super().exit_config_mode(exit_config=exit_config, pattern=pattern)

    def check_config_mode(self, check_string: str = "#", pattern: str = "") -> bool:
        """Checks whether in configuration mode. Returns a boolean."""

        return super().check_config_mode(check_string=check_string, pattern=pattern)

    def save_config(
        self,
        cmd: str = "copy running startup",
        confirm: bool = True,
        confirm_response: str = "y",
    ) -> str:
        """Save Config for 6WIND"""

        return super().save_config(
            cmd=cmd, confirm=confirm, confirm_response=confirm_response
        )

    def check_enable_mode(self, *args: Any, **kwargs: Any) -> bool:
        """6WIND has no enable mode."""

        return True

    def enable(self, *args: Any, **kwargs: Any) -> str:
        """6WIND has no enable mode."""

        return ""

    def exit_enable_mode(self, *args: Any, **kwargs: Any) -> str:
        """6WIND has no enable mode."""

        return ""


class SixwindOSSSH(SixwindOSBase):

    pass
