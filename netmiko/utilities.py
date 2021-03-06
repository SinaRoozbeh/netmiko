"""Miscellaneous utility functions."""
from glob import glob
import sys
import io
import os
import re
from pathlib import Path
import functools
from datetime import datetime

from typing import AnyStr
from typing import Dict, List, Union, Callable, Any, Optional, Tuple
from typing import TYPE_CHECKING

from netmiko._textfsm import _clitable as clitable
from netmiko._textfsm._clitable import CliTableError

if TYPE_CHECKING:
    from netmiko import BaseConnection
    from netmiko._textfsm._clitable import CliTable

    # from pathlib import PosixPath

try:
    from ttp import ttp

    TTP_INSTALLED = True

except ImportError:
    TTP_INSTALLED = False

try:
    from genie.conf.base import Device
    from genie.libs.parser.utils import get_parser
    from pyats.datastructures import AttrDict

    GENIE_INSTALLED = True
except ImportError:
    GENIE_INSTALLED = False

# If we are on python < 3.7, we need to force the import of importlib.resources backport
try:
    from importlib.resources import path as importresources_path  # type: ignore
except ModuleNotFoundError:
    from importlib_resources import path as importresources_path

try:
    import serial.tools.list_ports

    PYSERIAL_INSTALLED = True
except ImportError:
    PYSERIAL_INSTALLED = False

# Dictionary mapping 'show run' for vendors with different command
SHOW_RUN_MAPPER = {
    "juniper": "show configuration",
    "juniper_junos": "show configuration",
    "extreme": "show configuration",
    "extreme_ers": "show running-config",
    "extreme_exos": "show configuration",
    "extreme_netiron": "show running-config",
    "extreme_nos": "show running-config",
    "extreme_slx": "show running-config",
    "extreme_vdx": "show running-config",
    "extreme_vsp": "show running-config",
    "extreme_wing": "show running-config",
    "hp_comware": "display current-configuration",
    "huawei": "display current-configuration",
    "fortinet": "show full-configuration",
    "checkpoint": "show configuration",
    "cisco_wlc": "show run-config",
    "enterasys": "show running-config",
    "dell_force10": "show running-config",
    "avaya_vsp": "show running-config",
    "avaya_ers": "show running-config",
    "brocade_vdx": "show running-config",
    "brocade_nos": "show running-config",
    "brocade_fastiron": "show running-config",
    "brocade_netiron": "show running-config",
    "alcatel_aos": "show configuration snapshot",
}

# Expand SHOW_RUN_MAPPER to include '_ssh' key
new_dict = {}
for k, v in SHOW_RUN_MAPPER.items():
    new_key = k + "_ssh"
    new_dict[k] = v
    new_dict[new_key] = v
SHOW_RUN_MAPPER = new_dict

# Default location of netmiko temp directory for netmiko tools
NETMIKO_BASE_DIR = "~/.netmiko"


def load_yaml_file(yaml_file: str) -> Any:
    """Read YAML file."""
    try:
        import yaml
    except ImportError:
        sys.exit("Unable to import yaml module.")
    try:
        with io.open(yaml_file, "rt", encoding="utf-8") as fname:
            return yaml.safe_load(fname)
    except IOError:
        sys.exit(f"Unable to open YAML file: {yaml_file}")


def load_devices(file_name: Optional[str] = None) -> Any:
    """Find and load .netmiko.yml file."""
    yaml_devices_file = find_cfg_file(file_name)
    return load_yaml_file(yaml_devices_file)


def find_cfg_file(file_name: Optional[str] = None) -> str:
    """
    Search for netmiko_tools inventory file in the following order:
    NETMIKO_TOOLS_CFG environment variable
    Current directory
    Home directory
    Look for file named: .netmiko.yml or netmiko.yml
    Also allow NETMIKO_TOOLS_CFG to point directly at a file
    """
    if file_name:
        if os.path.isfile(file_name):
            return file_name
    optional_path = os.environ.get("NETMIKO_TOOLS_CFG", "")
    if os.path.isfile(optional_path):
        return optional_path
    search_paths = [optional_path, ".", os.path.expanduser("~")]
    # Filter optional_path if null
    search_paths = [path for path in search_paths if path]
    for path in search_paths:
        files = glob(f"{path}/.netmiko.yml") + glob(f"{path}/netmiko.yml")
        if files:
            return files[0]
    raise IOError(
        ".netmiko.yml file not found in NETMIKO_TOOLS environment variable directory,"
        " current directory, or home directory."
    )


def display_inventory(my_devices: Dict[str, Any]) -> None:
    """Print out inventory devices and groups."""
    inventory_groups = ["all"]
    inventory_devices = []
    for k, v in my_devices.items():
        if isinstance(v, list):
            inventory_groups.append(k)
        elif isinstance(v, dict):
            inventory_devices.append((k, v["device_type"]))

    inventory_groups.sort()
    inventory_devices.sort(key=lambda x: x[0])
    print("\nDevices:")
    print("-" * 40)
    for a_device, device_type in inventory_devices:
        device_type = f"  ({device_type})"
        print(f"{a_device:<25}{device_type:>15}")
    print("\n\nGroups:")
    print("-" * 40)
    for a_group in inventory_groups:
        print(a_group)
    print()


def obtain_all_devices(my_devices: Dict[str, Any]) -> Dict[str, Any]:
    """Dynamically create 'all' group."""
    new_devices = {}
    for device_name, device_or_group in my_devices.items():
        # Skip any groups
        if not isinstance(device_or_group, list):
            new_devices[device_name] = device_or_group
    return new_devices


def obtain_netmiko_filename(device_name: str) -> str:
    """Create file name based on device_name."""
    _, netmiko_full_dir = find_netmiko_dir()
    return f"{netmiko_full_dir}/{device_name}.txt"


def write_tmp_file(device_name: str, output: str) -> str:
    file_name = obtain_netmiko_filename(device_name)
    with open(file_name, "w") as f:
        f.write(output)
    return file_name


def ensure_dir_exists(verify_dir: str) -> None:
    """Ensure directory exists. Create if necessary."""
    if not os.path.exists(verify_dir):
        # Doesn't exist create dir
        os.makedirs(verify_dir)
    else:
        # Exists
        if not os.path.isdir(verify_dir):
            # Not a dir, raise an exception
            raise ValueError(f"{verify_dir} is not a directory")


def find_netmiko_dir() -> Tuple[str, str]:
    """Check environment first, then default dir"""
    try:
        netmiko_base_dir = os.environ["NETMIKO_DIR"]
    except KeyError:
        netmiko_base_dir = NETMIKO_BASE_DIR
    netmiko_base_dir = os.path.expanduser(netmiko_base_dir)
    if netmiko_base_dir == "/":
        raise ValueError("/ cannot be netmiko_base_dir")
    netmiko_full_dir = f"{netmiko_base_dir}/tmp"
    return (netmiko_base_dir, netmiko_full_dir)


def write_bytes(out_data: AnyStr, encoding: str = "ascii") -> bytes:
    if sys.version_info[0] >= 3:
        if isinstance(out_data, type("")):
            if encoding == "utf-8":
                return out_data.encode("utf-8")
            else:
                return out_data.encode("ascii", "ignore")
        elif isinstance(out_data, type(b"")):
            return out_data
    msg = "Invalid value for out_data neither unicode nor byte string"
    raise ValueError(msg)


def check_serial_port(name: str) -> str:
    """returns valid COM Port."""

    if not PYSERIAL_INSTALLED:
        msg = (
            "\npyserial is not installed. Please PIP install pyserial:\n\n"
            "pip install pyserial\n\n"
        )
        raise ValueError(msg)

    try:
        cdc = next(serial.tools.list_ports.grep(name))
        comm_port = cdc[0]
        assert isinstance(comm_port, str)
        return comm_port
    except StopIteration:
        msg = f"device {name} not found. "
        msg += "available devices are: "
        ports = list(serial.tools.list_ports.comports())
        for p in ports:
            msg += f"{str(p)},"
        raise ValueError(msg)


def get_template_dir(_skip_ntc_package: bool = False) -> str:
    """
    Find and return the directory containing the TextFSM index file.

    Order of preference is:
    1) Find directory in `NET_TEXTFSM` Environment Variable.
    2) Check for pip installed `ntc-templates` location in this environment.
    3) ~/ntc-templates/templates.

    If `index` file is not found in any of these locations, raise ValueError

    :return: directory containing the TextFSM index file

    """

    msg = """
Directory containing TextFSM index file not found.

Please set the NET_TEXTFSM environment variable to point at the directory containing your TextFSM
index file.

Alternatively, `pip install ntc-templates` (if using ntc-templates).

"""

    # Try NET_TEXTFSM environment variable
    template_dir = os.environ.get("NET_TEXTFSM")
    if template_dir is not None:
        template_dir = os.path.expanduser(template_dir)
        index = os.path.join(template_dir, "index")
        if not os.path.isfile(index):
            # Assume only base ./ntc-templates specified
            template_dir = os.path.join(template_dir, "templates")

    else:
        # Try 'pip installed' ntc-templates
        try:
            with importresources_path(
                package="ntc_templates", resource="templates"
            ) as posix_path:
                # Example: /opt/venv/netmiko/lib/python3.8/site-packages/ntc_templates/templates
                template_dir = str(posix_path)
                # This is for Netmiko automated testing
                if _skip_ntc_package:
                    raise ModuleNotFoundError()

        except ModuleNotFoundError:
            # Finally check in ~/ntc-templates/templates
            home_dir = os.path.expanduser("~")
            template_dir = os.path.join(home_dir, "ntc-templates", "templates")

    index = os.path.join(template_dir, "index")
    if not os.path.isdir(template_dir) or not os.path.isfile(index):
        raise ValueError(msg)
    return os.path.abspath(template_dir)


def clitable_to_dict(cli_table: "CliTable") -> List[Dict[str, Any]]:
    """Converts TextFSM cli_table object to list of dictionaries."""
    objs = []
    for row in cli_table:
        temp_dict = {}
        for index, element in enumerate(row):
            temp_dict[cli_table.header[index].lower()] = element
        objs.append(temp_dict)
    return objs


def _textfsm_parse(
    textfsm_obj: "CliTable",
    raw_output: str,
    attrs: Dict[str, Any],
    template_file: Optional[str] = None,
) -> Union[List[Dict[str, Any]], str]:
    """Perform the actual TextFSM parsing using the CliTable object."""
    try:
        # Parse output through template
        if template_file is not None:
            textfsm_obj.ParseCmd(raw_output, templates=template_file)  # type: ignore
        else:
            textfsm_obj.ParseCmd(raw_output, attrs)  # type: ignore
        structured_data = clitable_to_dict(textfsm_obj)
        if structured_data == []:
            assert isinstance(raw_output, str)
            return raw_output
        else:
            assert isinstance(structured_data, list)
            return structured_data
    except (FileNotFoundError, CliTableError):
        return raw_output


def get_structured_data(
    raw_output: str,
    platform: Optional[str] = None,
    command: Optional[str] = None,
    template: Optional[str] = None,
) -> Union[List[Dict[str, Any]], str]:
    """
    Convert raw CLI output to structured data using TextFSM template.

    You can use a straight TextFSM file i.e. specify "template". If no template is specified,
    then you must use an CliTable index file.
    """
    if platform is None or command is None:
        attrs = {}
    else:
        attrs = {"Command": command, "Platform": platform}

    if template is None:
        if attrs == {}:
            raise ValueError(
                "Either 'platform/command' or 'template' must be specified."
            )
        template_dir = get_template_dir()
        index_file = os.path.join(template_dir, "index")
        textfsm_obj = clitable.CliTable(index_file, template_dir)
        return _textfsm_parse(textfsm_obj, raw_output, attrs)
    else:
        template_path = Path(os.path.expanduser(template))
        template_file = template_path.name
        template_dir_path = template_path.parents[0]
        # CliTable with no index will fall-back to a TextFSM parsing behavior
        textfsm_obj = clitable.CliTable(template_dir=template_dir_path)
        return _textfsm_parse(
            textfsm_obj, raw_output, attrs, template_file=template_file
        )


def get_structured_data_ttp(
    raw_output: str, template: Optional[str] = None
) -> Union[List[Dict[str, Any]], str]:
    """
    Convert raw CLI output to structured data using TTP template.

    You can use a straight TextFSM file i.e. specify "template"
    """
    if not TTP_INSTALLED:
        msg = "\nTTP is not installed. Please PIP install ttp:\n" "pip install ttp\n"
        raise ValueError(msg)

    try:
        if template:
            ttp_parser = ttp(data=raw_output, template=template)
            ttp_parser.parse(one=True)
            ttp_output = ttp_parser.result(format="raw")
            # Strip off outer TTP list-of-lists
            ttp_output = ttp_output[0][0]
            if ttp_output == {}:
                return raw_output
            else:
                assert isinstance(ttp_output, list)
                return ttp_output
    except Exception:
        pass

    return raw_output


def get_structured_data_genie(
    raw_output: str, platform: str, command: str
) -> Union[Dict[str, Any], str]:
    if not sys.version_info >= (3, 4):
        raise ValueError("Genie requires Python >= 3.4")

    if not GENIE_INSTALLED:
        msg = (
            "\nGenie and PyATS are not installed. Please PIP install both Genie and PyATS:\n"
            "pip install genie\npip install pyats\n"
        )
        raise ValueError(msg)

    if "cisco" not in platform:
        return raw_output

    genie_device_mapper = {
        "cisco_ios": "ios",
        "cisco_xe": "iosxe",
        "cisco_xr": "iosxr",
        "cisco_nxos": "nxos",
        "cisco_asa": "asa",
    }

    os = None
    # platform might be _ssh, _telnet, _serial strip that off
    if platform.count("_") > 1:
        base_platform_list = platform.split("_")[:-1]
        base_platform = "_".join(base_platform_list)
    else:
        base_platform = platform

    os = genie_device_mapper.get(base_platform)
    if not os:
        assert isinstance(raw_output, str)
        return raw_output

    # Genie specific construct for doing parsing (based on Genie in Ansible)
    device = Device("new_device", os=os)
    device.custom.setdefault("abstraction", {})
    device.custom["abstraction"]["order"] = ["os"]
    device.cli = AttrDict({"execute": None})
    try:
        # Test whether there is a parser for given command (return Exception if fails)
        get_parser(command, device)
        parsed_output = device.parse(command, output=raw_output)
        assert isinstance(parsed_output, dict)
        return parsed_output
    except Exception:
        return raw_output


def select_cmd_verify(func: Callable[..., Any]) -> Callable[..., Any]:
    """Override function cmd_verify argument with global setting."""

    @functools.wraps(func)
    def wrapper_decorator(self: "BaseConnection", *args: Any, **kwargs: Any) -> Any:
        if self.global_cmd_verify is not None:
            kwargs["cmd_verify"] = self.global_cmd_verify
        return func(self, *args, **kwargs)

    return wrapper_decorator


def m_exec_time(func: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(func)
    def wrapper_decorator(self: object, *args: Any, **kwargs: Any) -> Any:
        start_time = datetime.now()
        result = func(self, *args, **kwargs)
        end_time = datetime.now()
        method_name = str(func)
        print(f"{method_name}: Elapsed time: {end_time - start_time}")
        return result

    return wrapper_decorator


def f_exec_time(func: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(func)
    def wrapper_decorator(*args: Any, **kwargs: Any) -> Any:
        start_time = datetime.now()
        result = func(*args, **kwargs)
        end_time = datetime.now()
        print(f"Elapsed time: {end_time - start_time}")
        return result

    return wrapper_decorator


def strip_ansi_escape_codes(string_buffer: str, return_str: str = "\n") -> str:
    """
    Remove any ANSI (VT100) ESC codes from the output

    http://en.wikipedia.org/wiki/ANSI_escape_code

    Note: this does not capture ALL possible ANSI Escape Codes only the ones
    I have encountered

    Current codes that are filtered:
    ESC = '\x1b' or chr(27)
    ESC = is the escape character [^ in hex ('\x1b')
    ESC[24;27H   Position cursor
    ESC[?25h     Show the cursor
    ESC[E        Next line (HP does ESC-E)
    ESC[K        Erase line from cursor to the end of line
    ESC[2K       Erase entire line
    ESC[1;24r    Enable scrolling from start to row end
    ESC[?6l      Reset mode screen with options 640 x 200 monochrome (graphics)
    ESC[?7l      Disable line wrapping
    ESC[2J       Code erase display
    ESC[00;32m   Color Green (30 to 37 are different colors) more general pattern is
                 ESC[\d\d;\d\dm and ESC[\d\d;\d\d;\d\dm
    ESC[6n       Get cursor position
    ESC[1D       Move cursor position leftward by x characters (1 in this case)

    HP ProCurve and Cisco SG300 require this (possible others).

    :param string_buffer: The string to be processed to remove ANSI escape codes
    :type string_buffer: str
    """  # noqa

    code_position_cursor = chr(27) + r"\[\d+;\d+H"
    code_show_cursor = chr(27) + r"\[\?25h"
    code_next_line = chr(27) + r"E"
    code_erase_line_end = chr(27) + r"\[K"
    code_erase_line = chr(27) + r"\[2K"
    code_erase_start_line = chr(27) + r"\[K"
    code_enable_scroll = chr(27) + r"\[\d+;\d+r"
    code_insert_line = chr(27) + r"\[(\d+)L"
    code_carriage_return = chr(27) + r"\[1M"
    code_disable_line_wrapping = chr(27) + r"\[\?7l"
    code_reset_mode_screen_options = chr(27) + r"\[\?\d+l"
    code_reset_graphics_mode = chr(27) + r"\[00m"
    code_erase_display = chr(27) + r"\[2J"
    code_erase_display_0 = chr(27) + r"\[J"
    code_graphics_mode = chr(27) + r"\[\d\d;\d\dm"
    code_graphics_mode2 = chr(27) + r"\[\d\d;\d\d;\d\dm"
    code_graphics_mode3 = chr(27) + r"\[(3|4)\dm"
    code_graphics_mode4 = chr(27) + r"\[(9|10)[0-7]m"
    code_get_cursor_position = chr(27) + r"\[6n"
    code_cursor_position = chr(27) + r"\[m"
    code_attrs_off = chr(27) + r"\[0m"
    code_reverse = chr(27) + r"\[7m"
    code_cursor_left = chr(27) + r"\[\d+D"

    code_set = [
        code_position_cursor,
        code_show_cursor,
        code_erase_line,
        code_enable_scroll,
        code_erase_start_line,
        code_carriage_return,
        code_disable_line_wrapping,
        code_erase_line_end,
        code_reset_mode_screen_options,
        code_reset_graphics_mode,
        code_erase_display,
        code_graphics_mode,
        code_graphics_mode2,
        code_graphics_mode3,
        code_graphics_mode4,
        code_get_cursor_position,
        code_cursor_position,
        code_erase_display,
        code_erase_display_0,
        code_attrs_off,
        code_reverse,
        code_cursor_left,
    ]

    # FIX - so that this is not a loop, but a single regex invocation using
    # a logical or (compare performance of the two).
    output = string_buffer
    for ansi_esc_code in code_set:
        output = re.sub(ansi_esc_code, "", output)

    # CODE_NEXT_LINE must substitute with return
    output = re.sub(code_next_line, return_str, output)

    # Aruba and ProCurve switches can use code_insert_line for <enter>
    insert_line_match = re.search(code_insert_line, output)
    if insert_line_match:
        # Substitute each insert_line with a new <enter>
        count = int(insert_line_match.group(1))
        output = re.sub(code_insert_line, count * return_str, output)

    return output
