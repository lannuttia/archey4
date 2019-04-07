#!/usr/bin/env python3


import os
import re
import sys

from enum import Enum
from glob import glob
from subprocess import CalledProcessError, DEVNULL, check_output

import distro

from output import Output
from configuration import Configuration
import entries
from constants import (
    COLOR_DICT,
    DE_DICT,
    WM_DICT,
)

# ---------- Global variables --------- #

# We create a global instance of our `Configuration` Class
CONFIG = Configuration()

# We'll list the running processes only one time
try:
    PROCESSES = check_output(
        ['ps', '-u' + str(os.getuid()) if os.getuid() != 0 else '-ax',
         '-o', 'comm', '--no-headers'], universal_newlines=True
    ).splitlines()

except FileNotFoundError:
    print('Please, install first `procps` on your distribution.',
          file=sys.stderr)
    exit()

# -------------- Entries -------------- #


class Distro:
    def __init__(self):
        self.value = '{0} [{1}]'.format(
            distro.name(pretty=True),
            check_output(
                ['uname', '-m'],
                universal_newlines=True
            ).rstrip()
        )


class WindowManager:
    def __init__(self):
        try:
            window_manager = re.search(
                '(?<=Name: ).*',
                check_output(
                    ['wmctrl', '-m'],
                    stderr=DEVNULL, universal_newlines=True
                )
            ).group(0)

        except (FileNotFoundError, CalledProcessError):
            for key, value in WM_DICT.items():
                if key in PROCESSES:
                    window_manager = value
                    break

            else:
                window_manager = CONFIG.get('default_strings')['not_detected']

        self.value = window_manager


class DesktopEnvironment:
    def __init__(self):
        for key, value in DE_DICT.items():
            if key in PROCESSES:
                desktop_environment = value
                break

        else:
            # Let's rely on an environment var if the loop above didn't `break`
            desktop_environment = os.getenv(
                'XDG_CURRENT_DESKTOP',
                CONFIG.get('default_strings')['not_detected']
            )

        self.value = desktop_environment


class Shell:
    def __init__(self):
        self.value = os.getenv(
            'SHELL',
            CONFIG.get('default_strings')['not_detected']
        )


class Terminal:
    def __init__(self):
        terminal = os.getenv(
            'TERM',
            CONFIG.get('default_strings')['not_detected']
        )

        # On systems with non-Unicode locales, we imitate '\u2588' character
        # ... with '#' to display the terminal colors palette.
        # This is the default option for backward compatibility.
        colors = ' '.join([
            '\x1b[0;3{0}m{1}\x1b[1;3{0}m{1}{2}'.format(
                i,
                '\u2588' if CONFIG.get('colors_palette')['use_unicode']
                else '#',
                COLOR_DICT['clear']
            ) for i in range(7, 0, -1)
        ])

        self.value = '{0} {1}'.format(terminal, colors)


class Temperature:
    def __init__(self):
        temps = []

        try:
            # Let's try to retrieve a value from the Broadcom chip on Raspberry
            temp = float(
                re.search(
                    r'\d+\.\d+',
                    check_output(
                        ['/opt/vc/bin/vcgencmd', 'measure_temp'],
                        stderr=DEVNULL, universal_newlines=True
                    )
                ).group(0)
            )

            temps.append(
                self._convert_to_fahrenheit(temp)
                if CONFIG.get('temperature')['use_fahrenheit'] else temp
            )

        except (FileNotFoundError, CalledProcessError):
            pass

        # Now we just check for values within files present in the path below
        for thermal_file in glob('/sys/class/thermal/thermal_zone*/temp'):
            with open(thermal_file) as file:
                try:
                    temp = float(file.read().strip()) / 1000

                except OSError:
                    continue

                if temp != 0.0:
                    temps.append(
                        self._convert_to_fahrenheit(temp)
                        if CONFIG.get('temperature')['use_fahrenheit']
                        else temp
                    )

        if temps:
            self.value = '{0}{1}{2}'.format(
                str(round(sum(temps) / len(temps), 1)),
                CONFIG.get('temperature')['char_before_unit'],
                'F' if CONFIG.get('temperature')['use_fahrenheit'] else 'C'
            )

            if len(temps) > 1:
                self.value += ' (Max. {0}{1}{2})'.format(
                    str(round(max(temps), 1)),
                    CONFIG.get('temperature')['char_before_unit'],
                    'F' if CONFIG.get('temperature')['use_fahrenheit'] else 'C'
                )

        else:
            self.value = CONFIG.get('default_strings')['not_detected']

    @staticmethod
    def _convert_to_fahrenheit(temp):
        """
        Simple Celsius to Fahrenheit conversion method
        """
        return temp * (9 / 5) + 32


# ----------- Classes Index ----------- #

class Classes(Enum):
    User = {
        'class': entries.User,
        'kwargs': {
            'not_detected': CONFIG.get('default_strings')['not_detected']
        }
    }
    Hostname = {'class': entries.Hostname}
    Model = {'class': entries.Model}
    Distro = {'class': Distro}
    Kernel = {'class': entries.Kernel}
    Uptime = {'class': entries.Uptime}
    WindowManager = {'class': WindowManager}
    DesktopEnvironment = {'class': DesktopEnvironment}
    Shell = {'class': Shell}
    Terminal = {'class': Terminal}
    Packages = {
        'class': entries.Packages,
        'kwargs': {
            'not_detected': CONFIG.get('default_strings')['not_detected']
        }
    }
    Temperature = {'class': Temperature}
    CPU = {'class': entries.CPU}
    GPU = {
         'class': entries.GPU,
         'kwargs': {
           'not_detected': CONFIG.get('default_strings')['not_detected']
         }
    }
    RAM = {'class': entries.RAM}
    Disk = {'class': entries.Disk}
    LAN_IP = {
        'class': entries.LanIp,
        'kwargs': {
            'ip_max_count': CONFIG.get('ip_settings')['lan_ip_max_count'],
            'no_address': CONFIG.get('default_strings')['no_address']
        }
    }
    WAN_IP = {
        'class': entries.WanIp,
        'kwargs': {
            'ipv6_support': CONFIG.get('ip_settings')['wan_ip_v6_support'],
            'ipv6_timeout': CONFIG.get('timeout')['ipv6_detection'],
            'ipv4_timeout': CONFIG.get('timeout')['ipv4_detection'],
            'no_address': CONFIG.get('default_strings')['no_address']
        }
    }


# ---------------- Main --------------- #

def main():
    output = Output()
    for key in Classes:
        if CONFIG.get('entries', {}).get(key.name, True):
            kwargs = key.value.get('kwargs', {})
            value = key.value['class'](**kwargs).value
            output.append(key.name, value)

    output.output()


if __name__ == '__main__':
    main()
