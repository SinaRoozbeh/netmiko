"""Netmiko driver for OneAccess ONEOS"""
from typing import Any
from netmiko.cisco_base_connection import CiscoBaseConnection
import time


class OneaccessOneOSBase(CiscoBaseConnection):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Init connection - similar as Cisco"""
        default_enter = kwargs.get("default_enter")
        kwargs["default_enter"] = "\r\n" if default_enter is None else default_enter
        super().__init__(*args, **kwargs)

    def session_preparation(self) -> None:
        """Prepare connection - disable paging"""
        self._test_channel_read()
        self.set_base_prompt()
        self.set_terminal_width(command="stty columns 255", pattern="stty")
        self.disable_paging(command="term len 0")
        # Clear the read buffer
        time.sleep(0.3 * self.global_delay_factor)
        self.clear_buffer()

    def save_config(
        self, cmd: str = "write mem", confirm: bool = False, confirm_response: str = ""
    ) -> str:
        """Save config: write mem"""
        return super().save_config(
            cmd=cmd, confirm=confirm, confirm_response=confirm_response
        )


class OneaccessOneOSSSH(OneaccessOneOSBase):
    pass


class OneaccessOneOSTelnet(OneaccessOneOSBase):
    pass
