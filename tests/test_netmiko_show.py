#!/usr/bin/env python
"""
setup_module: setup variables for later use.

test_disable_paging: disable paging
test_ssh_connect: verify ssh connectivity
test_send_command: send a command
test_send_command_timing: send a command
test_base_prompt: test the base prompt
test_strip_prompt: test removing the prompt
test_strip_command: test stripping extraneous info after sending a command
test_normalize_linefeeds: ensure \n is the only line termination character in output
test_clear_buffer: clear text buffer
test_enable_mode: verify enter enable mode
test_disconnect: cleanly disconnect the SSH session
"""
import pytest
import time
import os
from datetime import datetime
from netmiko.utilities import select_cmd_verify


@select_cmd_verify
def bogus_func(obj, *args, **kwargs):
    """Function that just returns the arguments modified by the decorator."""
    return (obj, args, kwargs)


def test_disable_paging(net_connect, commands, expected_responses):
    """Verify paging is disabled by looking for string after when paging would normally occur."""
    # FIX: these really shouldn't be necessary.
    if net_connect.device_type == "arista_eos":
        # Arista logging buffer gets enormous
        net_connect.send_command("clear logging")
    elif net_connect.device_type == "arista_eos":
        # NX-OS logging buffer gets enormous (NX-OS fails when testing very high-latency +
        # packet loss)
        net_connect.send_command("clear logging logfile")
    multiple_line_output = net_connect.send_command(commands["extended_output"])
    assert expected_responses["multiple_line_output"] in multiple_line_output


def test_terminal_width(net_connect, commands, expected_responses):
    """Verify long commands work properly."""
    wide_command = commands.get("wide_command")
    if wide_command:
        net_connect.send_command(wide_command)
    assert True


def test_ssh_connect(net_connect, commands, expected_responses):
    """Verify the connection was established successfully."""
    show_version = net_connect.send_command(commands["version"])
    assert expected_responses["version_banner"] in show_version


def test_ssh_connect_cm(net_connect_cm, commands, expected_responses):
    """Test the context manager."""
    prompt_str = net_connect_cm
    assert expected_responses["base_prompt"] in prompt_str


def test_send_command_timing(net_connect, commands, expected_responses):
    """Verify a command can be sent down the channel successfully."""
    time.sleep(1)
    net_connect.clear_buffer()
    # Force verification of command echo
    show_ip = net_connect.send_command_timing(commands["basic"], cmd_verify=True)
    assert expected_responses["interface_ip"] in show_ip


def test_send_command_timing_no_cmd_verify(net_connect, commands, expected_responses):
    # Skip devices that are performance optimized (i.e. cmd_verify is required there)
    if net_connect.fast_cli is True:
        assert pytest.skip()
    time.sleep(1)
    net_connect.clear_buffer()
    # cmd_verify=False is the default
    show_ip = net_connect.send_command_timing(commands["basic"], cmd_verify=False)
    assert expected_responses["interface_ip"] in show_ip


def test_send_command(net_connect, commands, expected_responses):
    """Verify a command can be sent down the channel successfully using send_command method."""
    net_connect.clear_buffer()
    show_ip_alt = net_connect.send_command(commands["basic"])
    assert expected_responses["interface_ip"] in show_ip_alt


def test_send_command_no_cmd_verify(net_connect, commands, expected_responses):
    # Skip devices that are performance optimized (i.e. cmd_verify is required there)
    if net_connect.fast_cli is True:
        assert pytest.skip()
    net_connect.clear_buffer()
    show_ip_alt = net_connect.send_command(commands["basic"], cmd_verify=False)
    assert expected_responses["interface_ip"] in show_ip_alt


def test_cmd_verify_decorator(net_connect_cmd_verify):
    obj = net_connect_cmd_verify
    # Global False should have precedence
    assert obj.global_cmd_verify is False
    (obj, args, kwargs) = bogus_func(net_connect_cmd_verify, cmd_verify=True)
    assert kwargs["cmd_verify"] is False
    (obj, args, kwargs) = bogus_func(net_connect_cmd_verify, cmd_verify=False)
    assert kwargs["cmd_verify"] is False

    # Global True should have precedence
    obj.global_cmd_verify = True
    assert obj.global_cmd_verify is True
    (obj, args, kwargs) = bogus_func(net_connect_cmd_verify, cmd_verify=True)
    assert kwargs["cmd_verify"] is True
    (obj, args, kwargs) = bogus_func(net_connect_cmd_verify, cmd_verify=False)
    assert kwargs["cmd_verify"] is True

    # None should track the local argument
    obj.global_cmd_verify = None
    assert obj.global_cmd_verify is None
    (obj, args, kwargs) = bogus_func(net_connect_cmd_verify, cmd_verify=True)
    assert kwargs["cmd_verify"] is True
    (obj, args, kwargs) = bogus_func(net_connect_cmd_verify, cmd_verify=False)
    assert kwargs["cmd_verify"] is False

    # Set it back to proper False value (so later tests aren't messed up).
    obj.global_cmd_verify = False


def test_send_command_global_cmd_verify(
    net_connect_cmd_verify, commands, expected_responses
):
    """
    Verify a command can be sent down the channel successfully using send_command method.

    Disable cmd_verify globally.
    """
    net_connect = net_connect_cmd_verify
    if net_connect.fast_cli is True:
        assert pytest.skip()
    net_connect.clear_buffer()
    # cmd_verify should be disabled globally at this point
    assert net_connect.global_cmd_verify is False
    show_ip_alt = net_connect.send_command(commands["basic"])
    assert expected_responses["interface_ip"] in show_ip_alt


def test_complete_on_space_disabled(net_connect, commands, expected_responses):
    """Verify complete on space is disabled."""
    # If complete on space is enabled will get re-written to "show configuration groups"
    if net_connect.device_type in ["juniper_junos", "nokia_sros"]:
        if (
            net_connect.device_type == "nokia_sros"
            and "@" not in net_connect.base_prompt
        ):
            # Only MD-CLI supports disable of command complete on space
            assert pytest.skip()
        cmd = commands.get("abbreviated_cmd")
        cmd_full = commands.get("abbreviated_cmd_full")
        net_connect.write_channel(f"{cmd}\n")
        output = net_connect.read_until_prompt()
        assert cmd_full not in output
    else:
        assert pytest.skip()


def test_send_command_textfsm(net_connect, commands, expected_responses):
    """Verify a command can be sent down the channel successfully using send_command method."""

    base_platform = net_connect.device_type
    if base_platform.count("_") >= 2:
        # Strip off the _ssh, _telnet, _serial
        base_platform = base_platform.split("_")[:-1]
        base_platform = "_".join(base_platform)
    if base_platform not in [
        "cisco_ios",
        "cisco_xe",
        "cisco_xr",
        "cisco_nxos",
        "arista_eos",
        "cisco_asa",
        "juniper_junos",
        "hp_procurve",
    ]:
        assert pytest.skip("TextFSM/ntc-templates not supported on this platform")
    else:
        time.sleep(1)
        net_connect.clear_buffer()
        fallback_cmd = commands.get("basic")
        command = commands.get("basic_textfsm", fallback_cmd)
        show_ip_alt = net_connect.send_command(command, use_textfsm=True)
        assert isinstance(show_ip_alt, list)


def test_send_command_ttp(net_connect):
    """Test TTP parsing works correctly."""

    base_platform = net_connect.device_type
    if base_platform.count("_") >= 2:
        # Strip off the _ssh, _telnet, _serial
        base_platform = base_platform.split("_")[:-1]
        base_platform = "_".join(base_platform)
    if base_platform not in ["cisco_ios"]:
        assert pytest.skip("TTP template not existing for this platform")
    else:
        time.sleep(1)
        net_connect.clear_buffer()

        # write a simple template to file
        ttp_raw_template = """interface {{ intf }}
 description {{ description }}
        """
        ttp_temp_filename = "show_run_interfaces.ttp"
        with open(ttp_temp_filename, "w") as writer:
            writer.write(ttp_raw_template)

        command = "show run"
        show_ip_alt = net_connect.send_command(
            command, use_ttp=True, ttp_template=ttp_temp_filename
        )
        os.remove(ttp_temp_filename)
        assert isinstance(show_ip_alt, list)
        # Ensures it isn't an empty data structure
        assert isinstance(show_ip_alt[0]["intf"], str)


def test_send_command_ttp_failed(net_connect):
    """Failed TTP parsing should return raw_output."""

    base_platform = net_connect.device_type
    if base_platform.count("_") >= 2:
        # Strip off the _ssh, _telnet, _serial
        base_platform = base_platform.split("_")[:-1]
        base_platform = "_".join(base_platform)
    if base_platform not in ["cisco_ios"]:
        assert pytest.skip("TTP template not existing for this platform")
    else:
        time.sleep(1)
        net_connect.clear_buffer()

        # Break template by having leading space
        ttp_raw_template = """   interface {{ intf }}
 description {{ description }}
        """
        ttp_temp_filename = "show_run_interfaces.ttp"
        with open(ttp_temp_filename, "w") as writer:
            writer.write(ttp_raw_template)

        command = "show run"
        show_ip_alt = net_connect.send_command(
            command, use_ttp=True, ttp_template=ttp_temp_filename
        )
        os.remove(ttp_temp_filename)
        assert isinstance(show_ip_alt, str)


def test_send_command_genie(net_connect, commands, expected_responses):
    """Verify a command can be sent down the channel successfully using send_command method."""

    base_platform = net_connect.device_type
    if base_platform.count("_") >= 2:
        # Strip off the _ssh, _telnet, _serial
        base_platform = base_platform.split("_")[:-1]
        base_platform = "_".join(base_platform)
    if base_platform not in [
        "cisco_ios",
        "cisco_xe",
        "cisco_xr",
        "cisco_nxos",
        "cisco_asa",
    ]:
        assert pytest.skip("Genie not supported on this platform")
    else:
        time.sleep(1)
        net_connect.clear_buffer()
        fallback_cmd = commands.get("basic")
        command = commands.get("basic_textfsm", fallback_cmd)
        show_ip_alt = net_connect.send_command(command, use_genie=True)
        assert isinstance(show_ip_alt, dict)


def test_base_prompt(net_connect, commands, expected_responses):
    """Verify the router prompt is detected correctly."""
    assert net_connect.base_prompt == expected_responses["base_prompt"]


def test_strip_prompt(net_connect, commands, expected_responses):
    """Ensure the router prompt is not in the command output."""

    if expected_responses["base_prompt"] == "":
        return
    show_ip = net_connect.send_command_timing(commands["basic"])
    show_ip_alt = net_connect.send_command(commands["basic"])
    assert expected_responses["base_prompt"] not in show_ip
    assert expected_responses["base_prompt"] not in show_ip_alt


def test_strip_command(net_connect, commands, expected_responses):
    """Ensure that the command that was executed does not show up in the command output."""
    show_ip = net_connect.send_command_timing(commands["basic"])
    show_ip_alt = net_connect.send_command(commands["basic"])

    # dlink_ds has an echo of the command in the command output
    if "dlink_ds" in net_connect.device_type:
        show_ip = "\n".join(show_ip.split("\n")[2:])
        show_ip_alt = "\n".join(show_ip_alt.split("\n")[2:])
    assert commands["basic"] not in show_ip
    assert commands["basic"] not in show_ip_alt


def test_normalize_linefeeds(net_connect, commands, expected_responses):
    """Ensure no '\r\n' sequences."""
    show_version = net_connect.send_command_timing(commands["version"])
    show_version_alt = net_connect.send_command(commands["version"])
    assert "\r\n" not in show_version
    assert "\r\n" not in show_version_alt


def test_clear_buffer(net_connect, commands, expected_responses):
    """Test that clearing the buffer works."""
    # Manually send a command down the channel so that data needs read.
    net_connect.write_channel(commands["basic"] + "\n")
    time.sleep(4)
    net_connect.clear_buffer()

    # Should not be anything there on the second pass
    clear_buffer_check = net_connect.clear_buffer()
    assert clear_buffer_check is None


def test_enable_mode(net_connect, commands, expected_responses):
    """
    Test entering enable mode

    Catch exception for devices that don't support enable
    """
    try:
        net_connect.enable()
        enable_prompt = net_connect.find_prompt()
        assert enable_prompt == expected_responses["enable_prompt"]
    except AttributeError:
        assert True


def test_disconnect(net_connect, commands, expected_responses):
    """Terminate the SSH session."""
    start_time = datetime.now()
    net_connect.disconnect()
    end_time = datetime.now()
    time_delta = end_time - start_time
    assert time_delta.total_seconds() < 8
    with pytest.raises(AttributeError) as e:  # noqa
        net_connect.channel.remote_conn


def test_disconnect_no_enable(net_connect_newconn, commands, expected_responses):
    """Terminate the SSH session from privilege level1"""
    net_connect = net_connect_newconn
    if "cisco_ios" in net_connect.device_type:
        net_connect.send_command_timing("disable")
        start_time = datetime.now()
        net_connect.disconnect()
        end_time = datetime.now()
        time_delta = end_time - start_time
        assert time_delta.total_seconds() < 5
        with pytest.raises(AttributeError) as e:  # noqa
            net_connect.channel.remote_conn
    else:
        assert True
