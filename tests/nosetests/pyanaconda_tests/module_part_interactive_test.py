#
# Copyright (C) 2019  Red Hat, Inc.
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
import unittest
from unittest.mock import Mock

from pyanaconda.core.constants import PARTITIONING_METHOD_INTERACTIVE
from pyanaconda.modules.common.containers import DeviceTreeContainer
from pyanaconda.modules.storage.devicetree.devicetree_interface import DeviceTreeInterface
from pyanaconda.modules.storage.partitioning.interactive import InteractivePartitioningModule
from pyanaconda.modules.storage.partitioning.interactive_interface import \
    InteractivePartitioningInterface
from pyanaconda.modules.storage.partitioning.interactive_partitioning import \
    InteractivePartitioningTask
from pyanaconda.modules.storage.partitioning.validate import StorageValidateTask

from tests.nosetests.pyanaconda_tests import patch_dbus_publish_object, check_task_creation


class InteractivePartitioningInterfaceTestCase(unittest.TestCase):
    """Test DBus interface of the interactive partitioning module."""

    def setUp(self):
        """Set up the module."""
        self.module = InteractivePartitioningModule()
        self.interface = InteractivePartitioningInterface(self.module)

    def publication_test(self):
        """Test the DBus representation."""
        self.assertIsInstance(self.module.for_publication(), InteractivePartitioningInterface)

    def method_property_test(self):
        """Test Method property."""
        self.assertEqual(self.interface.PartitioningMethod, PARTITIONING_METHOD_INTERACTIVE)

    @patch_dbus_publish_object
    def get_device_tree_test(self, publisher):
        """Test GetDeviceTree."""
        DeviceTreeContainer._counter = 0
        self.module.on_storage_reset(Mock())

        tree_path = self.interface.GetDeviceTree()

        publisher.assert_called_once()
        object_path, obj = publisher.call_args[0]

        self.assertEqual(tree_path, object_path)
        self.assertIsInstance(obj, DeviceTreeInterface)

        self.assertEqual(obj.implementation, self.module._device_tree_module)
        self.assertEqual(obj.implementation.storage, self.module.storage)
        self.assertTrue(tree_path.endswith("/DeviceTree/1"))

        publisher.reset_mock()

        self.assertEqual(tree_path, self.interface.GetDeviceTree())
        self.assertEqual(tree_path, self.interface.GetDeviceTree())
        self.assertEqual(tree_path, self.interface.GetDeviceTree())

        publisher.assert_not_called()

    @patch_dbus_publish_object
    def configure_with_task_test(self, publisher):
        """Test ConfigureWithTask."""
        self.module.on_storage_reset(Mock())
        task_path = self.interface.ConfigureWithTask()

        obj = check_task_creation(self, task_path, publisher, InteractivePartitioningTask)

        self.assertEqual(obj.implementation._storage, self.module.storage)

    @patch_dbus_publish_object
    def validate_with_task_test(self, publisher):
        """Test ValidateWithTask."""
        self.module.on_storage_reset(Mock())
        task_path = self.interface.ValidateWithTask()

        obj = check_task_creation(self, task_path, publisher, StorageValidateTask)

        self.assertEqual(obj.implementation._storage, self.module.storage)
