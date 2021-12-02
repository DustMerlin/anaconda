#
# Copyright (C) 2018  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): Vendula Poncova <vponcova@redhat.com>
#
import os
import tempfile
import unittest
import pytest

from shutil import copytree, copyfile
from unittest.mock import patch

from dasbus.structure import compare_data
from dasbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.core.constants import TIME_SOURCE_SERVER, TIME_SOURCE_POOL
from pyanaconda.modules.common.constants.services import TIMEZONE
from pyanaconda.modules.common.errors.installation import TimezoneConfigurationError
from pyanaconda.modules.common.structures.requirement import Requirement
from pyanaconda.modules.common.structures.timezone import TimeSourceData
from pyanaconda.modules.timezone.installation import ConfigureNTPTask, ConfigureTimezoneTask
from pyanaconda.modules.common.structures.kickstart import KickstartReport
from pyanaconda.modules.timezone.timezone import TimezoneService
from pyanaconda.modules.timezone.timezone_interface import TimezoneInterface
from pyanaconda.ntp import NTP_CONFIG_FILE, NTPconfigError
from tests.unit_tests.pyanaconda_tests import check_kickstart_interface, \
    patch_dbus_publish_object, PropertiesChangedCallback, check_task_creation_list, \
    check_dbus_property


class TimezoneInterfaceTestCase(unittest.TestCase):
    """Test DBus interface for the timezone module."""

    def setUp(self):
        """Set up the timezone module."""
        # Set up the timezone module.
        self.timezone_module = TimezoneService()
        self.timezone_interface = TimezoneInterface(self.timezone_module)

        # Connect to the properties changed signal.
        self.callback = PropertiesChangedCallback()
        self.timezone_interface.PropertiesChanged.connect(self.callback)

    def _check_dbus_property(self, *args, **kwargs):
        check_dbus_property(
            self,
            TIMEZONE,
            self.timezone_interface,
            *args, **kwargs
        )

    def test_kickstart_properties(self):
        """Test kickstart properties."""
        assert self.timezone_interface.KickstartCommands == ["timezone", "timesource"]
        assert self.timezone_interface.KickstartSections == []
        assert self.timezone_interface.KickstartAddons == []
        self.callback.assert_not_called()

    def test_timezone_property(self):
        """Test the Timezone property."""
        self.timezone_interface.SetTimezone("Europe/Prague")
        assert self.timezone_interface.Timezone == "Europe/Prague"
        self.callback.assert_called_once_with(
            TIMEZONE.interface_name, {'Timezone': 'Europe/Prague'}, [])

    def test_utc_property(self):
        """Test the IsUtc property."""
        self.timezone_interface.SetIsUTC(True)
        assert self.timezone_interface.IsUTC == True
        self.callback.assert_called_once_with(TIMEZONE.interface_name, {'IsUTC': True}, [])

    def test_ntp_property(self):
        """Test the NTPEnabled property."""
        self.timezone_interface.SetNTPEnabled(False)
        assert self.timezone_interface.NTPEnabled == False
        self.callback.assert_called_once_with(TIMEZONE.interface_name, {'NTPEnabled': False}, [])

    def test_time_sources_property(self):
        """Test the TimeSources property."""
        server = {
            "type": get_variant(Str, TIME_SOURCE_SERVER),
            "hostname": get_variant(Str, "ntp.cesnet.cz"),
            "options": get_variant(List[Str], ["iburst"]),
        }

        pool = {
            "type": get_variant(Str, TIME_SOURCE_POOL),
            "hostname": get_variant(Str, "0.fedora.pool.ntp.org"),
            "options": get_variant(List[Str], []),
        }

        self._check_dbus_property(
            "TimeSources",
            [server, pool]
        )

    def _test_kickstart(self, ks_in, ks_out):
        check_kickstart_interface(self, self.timezone_interface, ks_in, ks_out)

    def test_no_kickstart(self):
        """Test with no kickstart."""
        ks_in = None
        ks_out = """
        # System timezone
        timezone America/New_York
        """
        self._test_kickstart(ks_in, ks_out)

    def test_kickstart_empty(self):
        """Test with empty string."""
        ks_in = ""
        ks_out = ""
        self._test_kickstart(ks_in, ks_out)

    def test_kickstart(self):
        """Test the timezone command."""
        ks_in = """
        timezone Europe/Prague
        """
        ks_out = """
        # System timezone
        timezone Europe/Prague
        """
        self._test_kickstart(ks_in, ks_out)

    def test_kickstart2(self):
        """Test the timezone command with flags."""
        ks_in = """
        timezone --utc --nontp Europe/Prague
        """
        ks_out = """
        timesource --ntp-disable
        # System timezone
        timezone Europe/Prague --utc
        """
        self._test_kickstart(ks_in, ks_out)

    def test_kickstart3(self):
        """Test the timezone command with ntp servers."""
        ks_in = """
        timezone --ntpservers ntp.cesnet.cz Europe/Prague
        """
        ks_out = """
        timesource --ntp-server=ntp.cesnet.cz
        # System timezone
        timezone Europe/Prague
        """
        self._test_kickstart(ks_in, ks_out)

    def test_kickstart_timesource_ntp_disabled(self):
        """Test the timesource command with ntp disabled."""
        ks_in = """
        timesource --ntp-disable
        """
        ks_out = """
        timesource --ntp-disable
        """
        self._test_kickstart(ks_in, ks_out)

    def test_kickstart_timesource_ntp_server(self):
        """Test the timesource command with ntp servers."""
        ks_in = """
        timesource --ntp-server ntp.cesnet.cz
        """
        ks_out = """
        timesource --ntp-server=ntp.cesnet.cz
        """
        self._test_kickstart(ks_in, ks_out)

    def test_kickstart_timesource_ntp_pool(self):
        """Test the timesource command with ntp pools."""
        ks_in = """
        timesource --ntp-pool ntp.cesnet.cz
        """
        ks_out = """
        timesource --ntp-pool=ntp.cesnet.cz
        """
        self._test_kickstart(ks_in, ks_out)

    def test_kickstart_timesource_nts(self):
        """Test the timesource command with the nts option."""
        ks_in = """
        timesource --ntp-pool ntp.cesnet.cz --nts
        """
        ks_out = """
        timesource --ntp-pool=ntp.cesnet.cz --nts
        """
        self._test_kickstart(ks_in, ks_out)

    def test_kickstart_timesource_all(self):
        """Test the timesource commands."""
        ks_in = """
        timesource --ntp-server ntp.cesnet.cz
        timesource --ntp-pool 0.fedora.pool.ntp.org
        """
        ks_out = """
        timesource --ntp-server=ntp.cesnet.cz
        timesource --ntp-pool=0.fedora.pool.ntp.org
        """
        self._test_kickstart(ks_in, ks_out)

    def test_kickstart_timezone_timesource(self):
        """Test the combination of timezone and timesource commands."""
        ks_in = """
        timezone --ntpservers ntp.cesnet.cz,0.fedora.pool.ntp.org Europe/Prague
        timesource --ntp-server ntp.cesnet.cz --nts
        timesource --ntp-pool 0.fedora.pool.ntp.org
        """
        ks_out = """
        timesource --ntp-server=ntp.cesnet.cz
        timesource --ntp-server=0.fedora.pool.ntp.org
        timesource --ntp-server=ntp.cesnet.cz --nts
        timesource --ntp-pool=0.fedora.pool.ntp.org
        # System timezone
        timezone Europe/Prague
        """
        self._test_kickstart(ks_in, ks_out)

    def test_collect_requirements(self):
        """Test the requirements of the Timezone module."""
        # Check the default requirements.
        requirements = Requirement.from_structure_list(
            self.timezone_interface.CollectRequirements()
        )
        assert len(requirements) == 1
        assert requirements[0].type == "package"
        assert requirements[0].name == "chrony"

        # Check requirements with disabled NTP service.
        self.timezone_interface.SetNTPEnabled(False)
        requirements = Requirement.from_structure_list(
            self.timezone_interface.CollectRequirements()
        )
        assert len(requirements) == 0

    @patch_dbus_publish_object
    def test_install_with_tasks_default(self, publisher):
        """Test install tasks - module in default state."""
        task_classes = [
            ConfigureTimezoneTask,
            ConfigureNTPTask,
        ]
        task_paths = self.timezone_interface.InstallWithTasks()
        task_objs = check_task_creation_list(self, task_paths, publisher, task_classes)

        # ConfigureTimezoneTask
        obj = task_objs[0]
        assert obj.implementation._timezone == "America/New_York"
        assert obj.implementation._is_utc == False
        # ConfigureNTPTask
        obj = task_objs[1]
        assert obj.implementation._ntp_enabled == True
        assert obj.implementation._ntp_servers == []

    @patch_dbus_publish_object
    def test_install_with_tasks_configured(self, publisher):
        """Test install tasks - module in configured state."""

        self.timezone_interface.SetIsUTC(True)
        self.timezone_interface.SetTimezone("Asia/Tokyo")
        self.timezone_interface.SetNTPEnabled(False)
        # --nontp and --ntpservers are mutually exclusive in kicstart but
        # there is no such enforcement in the module so for testing this is ok

        server = TimeSourceData()
        server.type = TIME_SOURCE_SERVER
        server.hostname = "clock1.example.com"
        server.options = ["iburst"]

        pool = TimeSourceData()
        pool.type = TIME_SOURCE_POOL
        pool.hostname = "clock2.example.com"

        self.timezone_interface.SetTimeSources(
            TimeSourceData.to_structure_list([server, pool])
        )

        task_classes = [
            ConfigureTimezoneTask,
            ConfigureNTPTask,
        ]
        task_paths = self.timezone_interface.InstallWithTasks()
        task_objs = check_task_creation_list(self, task_paths, publisher, task_classes)

        # ConfigureTimezoneTask
        obj = task_objs[0]
        assert obj.implementation._timezone == "Asia/Tokyo"
        assert obj.implementation._is_utc == True

        # ConfigureNTPTask
        obj = task_objs[1]
        assert obj.implementation._ntp_enabled == False
        assert len(obj.implementation._ntp_servers) == 2
        assert compare_data(obj.implementation._ntp_servers[0], server)
        assert compare_data(obj.implementation._ntp_servers[1], pool)

    def test_deprecated_warnings(self):
        response = self.timezone_interface.ReadKickstart("timezone --isUtc Europe/Bratislava")
        report = KickstartReport.from_structure(response)

        warning = "The option --isUtc will be deprecated in future releases. " \
                  "Please modify your kickstart file to replace this option with " \
                  "its preferred alias --utc."

        assert len(report.warning_messages) == 1
        assert report.warning_messages[0].message == warning


class TimezoneTasksTestCase(unittest.TestCase):
    """Test the D-Bus Timezone (Timezone only) tasks."""

    def test_timezone_task_success(self):
        """Test the "full success" code paths in timezone D-Bus task."""
        self._test_timezone_inputs(input_zone="Europe/Prague",
                                   input_isutc=False,
                                   make_adjtime=True,
                                   make_zoneinfo=True,
                                   expected_symlink="../usr/share/zoneinfo/Europe/Prague",
                                   expected_adjtime_last_line="LOCAL")
        self._test_timezone_inputs(input_zone="Africa/Bissau",
                                   input_isutc=True,
                                   make_adjtime=True,
                                   make_zoneinfo=True,
                                   expected_symlink="../usr/share/zoneinfo/Africa/Bissau",
                                   expected_adjtime_last_line="UTC")
        self._test_timezone_inputs(input_zone="Etc/GMT-12",
                                   input_isutc=True,
                                   make_adjtime=True,
                                   make_zoneinfo=True,
                                   expected_symlink="../usr/share/zoneinfo/Etc/GMT-12",
                                   expected_adjtime_last_line="UTC")
        self._test_timezone_inputs(input_zone="Etc/GMT+3",
                                   input_isutc=True,
                                   make_adjtime=False,
                                   make_zoneinfo=True,
                                   expected_symlink="../usr/share/zoneinfo/Etc/GMT+3",
                                   expected_adjtime_last_line="UTC")

    def test_timezone_task_correction(self):
        """Test nonsensical time zone correction in timezone D-Bus task."""
        self._test_timezone_inputs(input_zone="",
                                   input_isutc=True,
                                   make_adjtime=True,
                                   make_zoneinfo=True,
                                   expected_symlink="../usr/share/zoneinfo/America/New_York",
                                   expected_adjtime_last_line="UTC")
        self._test_timezone_inputs(input_zone="BahBlah",
                                   input_isutc=True,
                                   make_adjtime=True,
                                   make_zoneinfo=True,
                                   expected_symlink="../usr/share/zoneinfo/America/New_York",
                                   expected_adjtime_last_line="UTC")
        self._test_timezone_inputs(input_zone=None,
                                   input_isutc=True,
                                   make_adjtime=True,
                                   make_zoneinfo=True,
                                   expected_symlink="../usr/share/zoneinfo/America/New_York",
                                   expected_adjtime_last_line="UTC")

    @patch('pyanaconda.modules.timezone.installation.arch.is_s390', return_value=True)
    def test_timezone_task_s390(self, mock_is_s390):
        """Test skipping writing /etc/adjtime on s390"""
        with tempfile.TemporaryDirectory() as sysroot:
            self._setup_environment(sysroot, False, True)
            self._execute_task(sysroot, "Africa/Bissau", False)
            self._check_timezone_symlink(sysroot, "../usr/share/zoneinfo/Africa/Bissau")
            assert not os.path.exists(sysroot + "/etc/adjtime")
        mock_is_s390.assert_called_once()
        # expected state: calling it only once in the check for architecture

    def test_timezone_task_timezone_missing(self):
        """Test failure when setting a valid but missing timezone."""
        with tempfile.TemporaryDirectory() as sysroot:
            self._setup_environment(sysroot, False, True)
            os.remove(sysroot + "/usr/share/zoneinfo/Asia/Ulaanbaatar")
            with self.assertLogs("anaconda.modules.timezone.installation", level="ERROR"):
                self._execute_task(sysroot, "Asia/Ulaanbaatar", False)
            assert not os.path.exists(sysroot + "/etc/localtime")

    @patch("pyanaconda.modules.timezone.installation.os.symlink", side_effect=OSError)
    def test_timezone_task_symlink_failure(self, mock_os_symlink):
        """Test failure when symlinking the time zone."""
        with tempfile.TemporaryDirectory() as sysroot:
            self._setup_environment(sysroot, False, True)
            with self.assertLogs("anaconda.modules.timezone.installation", level="ERROR"):
                self._execute_task(sysroot, "Asia/Ulaanbaatar", False)
            assert not os.path.exists(sysroot + "/etc/localtime")

    @patch('pyanaconda.modules.timezone.installation.open', side_effect=OSError)
    def test_timezone_task_write_adjtime_failure(self, mock_open):
        """Test failure when writing the /etc/adjtime file."""
        # Note the first open() in the target code should not fail due to mocking, but it would
        # anyway due to /etc/adjtime missing from env. setup, so it's ok if it does.
        with tempfile.TemporaryDirectory() as sysroot:
            with pytest.raises(TimezoneConfigurationError):
                self._setup_environment(sysroot, False, True)
                self._execute_task(sysroot, "Atlantic/Faroe", False)
            assert not os.path.exists(sysroot + "/etc/adjtime")
            assert os.path.exists(sysroot + "/etc/localtime")

    def _test_timezone_inputs(self, input_zone, input_isutc, make_adjtime, make_zoneinfo,
                              expected_symlink, expected_adjtime_last_line):
        with tempfile.TemporaryDirectory() as sysroot:
            self._setup_environment(sysroot, make_adjtime, make_zoneinfo)
            self._execute_task(sysroot, input_zone, input_isutc)
            self._check_timezone_symlink(sysroot, expected_symlink)
            self._check_utc_lastline(sysroot, expected_adjtime_last_line)

    def _setup_environment(self, sysroot, make_adjtime, make_zoneinfo):
        os.mkdir(sysroot + "/etc")
        if make_adjtime:
            copyfile("/etc/adjtime", sysroot + "/etc/adjtime")
        if make_zoneinfo:
            copytree("/usr/share/zoneinfo", sysroot + "/usr/share/zoneinfo")

    def _execute_task(self, sysroot, timezone, is_utc):
        task = ConfigureTimezoneTask(
            sysroot=sysroot,
            timezone=timezone,
            is_utc=is_utc
        )
        task.run()

    def _check_timezone_symlink(self, sysroot, expected_symlink):
        """Check if the right timezone is set as the symlink."""
        link_target = os.readlink(sysroot + "/etc/localtime")
        assert expected_symlink == link_target

    def _check_utc_lastline(self, sysroot, expected_adjtime_last_line):
        """Check that the UTC was saved"""
        with open(os.path.normpath(sysroot + "/etc/adjtime"), "r") as fobj:
            # Careful, this can die on huge files accidentally stuffed there instead.
            lines = fobj.readlines()
            # It must be last line because we write it so and nothing should have touched
            # it in test environment.
            last_line = lines[-1].strip()
            assert expected_adjtime_last_line == last_line


class NTPTasksTestCase(unittest.TestCase):
    """Test the D-Bus NTP tasks from the Timezone module."""

    def test_ntp_task_success(self):
        """Test the success cases for NTP setup D-Bus task."""
        self._test_ntp_inputs(
            make_chronyd=False,
            ntp_enabled=False
        )
        self._test_ntp_inputs(
            make_chronyd=False,
            ntp_enabled=True
        )

    def test_ntp_overwrite(self):
        """Test overwriting existing config for NTP setup D-Bus task."""
        self._test_ntp_inputs(
            make_chronyd=True,
            ntp_enabled=True
        )
        self._test_ntp_inputs(
            make_chronyd=True,
            ntp_enabled=False
        )

    def test_ntp_service(self):
        """Test enabling of the NTP service in a D-Bus task."""
        self._test_ntp_inputs(
            ntp_enabled=False,
            ntp_installed=True
        )
        self._test_ntp_inputs(
            ntp_enabled=True,
            ntp_installed=True
        )

    @patch("pyanaconda.modules.timezone.installation.ntp.save_servers_to_config")
    def test_ntp_save_failure(self, save_servers):
        """Test failure when saving NTP config in D-Bus task."""
        save_servers.side_effect = NTPconfigError

        with self.assertLogs("anaconda.modules.timezone.installation", level="WARNING"):
            self._test_ntp_inputs(
                make_chronyd=True,
                ntp_enabled=True,
                ntp_config_error=True
            )

        with self.assertLogs("anaconda.modules.timezone.installation", level="WARNING"):
            self._test_ntp_inputs(
                make_chronyd=False,
                ntp_enabled=True,
                ntp_config_error=True
            )

        save_servers.assert_called()

    def _get_test_sources(self):
        """Get a list of sources"""
        server = TimeSourceData()
        server.type = TIME_SOURCE_SERVER
        server.hostname = "unique.ntp.server"
        server.options = ["iburst"]

        pool = TimeSourceData()
        pool.type = TIME_SOURCE_POOL
        pool.hostname = "another.unique.server"

        return [server, pool]

    def _get_expected_lines(self):
        return [
            "server unique.ntp.server iburst\n",
            "pool another.unique.server\n"
        ]

    def _test_ntp_inputs(self, make_chronyd=False, ntp_enabled=True, ntp_installed=False,
                         ntp_config_error=False):
        ntp_servers = self._get_test_sources()
        expected_lines = self._get_expected_lines()

        with tempfile.TemporaryDirectory() as sysroot:
            self._setup_environment(sysroot, make_chronyd)

            with patch("pyanaconda.modules.timezone.installation.util") as mock_util:
                mock_util.is_service_installed.return_value = ntp_installed
                self._execute_task(sysroot, ntp_enabled, ntp_servers)
                self._validate_ntp_service(sysroot, mock_util, ntp_installed, ntp_enabled)

            if ntp_config_error:
                return

            self._validate_ntp_config(sysroot, make_chronyd, ntp_enabled, expected_lines)

    def _setup_environment(self, sysroot, make_chronyd):
        os.mkdir(sysroot + "/etc")
        if make_chronyd:
            copyfile(NTP_CONFIG_FILE, sysroot + NTP_CONFIG_FILE)

    def _execute_task(self, sysroot, ntp_enabled, ntp_servers):
        task = ConfigureNTPTask(
            sysroot=sysroot,
            ntp_enabled=ntp_enabled,
            ntp_servers=ntp_servers
        )
        task.run()

    def _validate_ntp_service(self, sysroot, mock_util, ntp_installed, ntp_enabled):
        mock_util.is_service_installed.assert_called_once_with(
            "chronyd", root=sysroot
        )

        if not ntp_installed:
            mock_util.enable_service.assert_not_called()
            mock_util.disable_service.assert_not_called()
        elif ntp_enabled:
            mock_util.enable_service.assert_called_once_with(
                "chronyd", root=sysroot
            )
            mock_util.disable_service.assert_not_called()
        else:
            mock_util.enable_service.assert_not_called()
            mock_util.disable_service.assert_called_once_with(
                "chronyd", root=sysroot
            )

    def _validate_ntp_config(self, sysroot, was_present, was_enabled, expected_lines):
        if was_enabled:
            with open(sysroot + NTP_CONFIG_FILE) as fobj:
                all_lines = fobj.readlines()

            for line in expected_lines:
                assert line in all_lines

        elif not was_present:
            assert not os.path.exists(sysroot + NTP_CONFIG_FILE)
