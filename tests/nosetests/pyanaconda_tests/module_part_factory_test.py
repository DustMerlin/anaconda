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

from pyanaconda.modules.storage.partitioning.base import PartitioningModule
from pyanaconda.modules.storage.partitioning.base_interface import PartitioningInterface
from pyanaconda.modules.storage.partitioning.constants import PartitioningMethod
from pyanaconda.modules.storage.partitioning.factory import PartitioningFactory


class PartitioningFactoryTestCase(unittest.TestCase):
    """Test the partitioning factory."""

    def create_partitioning_test(self):
        """Test create_partitioning."""
        for method in PartitioningMethod:
            module = PartitioningFactory.create_partitioning(method)
            self.assertIsInstance(module, PartitioningModule)
            self.assertIsInstance(module.for_publication(), PartitioningInterface)
            self.assertEqual(module.partitioning_method, method)

    def failed_partitioning_test(self):
        """Test failed create_partitioning."""
        with self.assertRaises(ValueError):
            PartitioningFactory.create_partitioning("INVALID")
