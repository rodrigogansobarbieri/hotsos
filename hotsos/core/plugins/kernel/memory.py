import os
import re

from hotsos.core.config import HotSOSConfig
from hotsos.core.utils import sorted_dict


class VMStat(object):

    def __init__(self):
        self._vmstat_info = {}

    @property
    def path(self):
        return os.path.join(HotSOSConfig.DATA_ROOT, 'proc/vmstat')

    @property
    def compaction_failures_percent(self):
        if not os.path.exists(self.path):
            return 0

        fail_count = self.compact_fail
        success_count = self.compact_success
        if not success_count:
            return 0

        return int(fail_count / (success_count / 100))

    def __getattr__(self, key):
        if key in self._vmstat_info:
            return self._vmstat_info[key]

        if not os.path.exists(self.path):
            return 0

        for line in open(self.path):
            if line.partition(" ")[0] == key:
                value = int(line.partition(" ")[2])
                self._vmstat_info[key] = value
                return value

        raise AttributeError('attribute {} not found in {}.'.
                             format(key, self.__class__.__name__))


class SlabInfo(object):

    def __init__(self, filter_names=None):
        self._filter_names = filter_names or []
        self._slab_info = []
        self._load_slab_info()

    @property
    def path(self):
        return os.path.join(HotSOSConfig.DATA_ROOT, "proc/slabinfo")

    @property
    def contents(self):
        return self._slab_info

    def _load_slab_info(self):
        """
        Returns a list with contents of the following columns from
        /proc/slabinfo:

            name
            num_objs
            objsize

        @param exclude_names: optional list of names to exclude.
        """
        for line in open(self.path):
            exclude = False
            for name in self._filter_names:
                if re.compile(r'^{}'.format(name)).search(line):
                    exclude = True
                    break

            if exclude:
                continue

            sections = line.split()
            if sections[0] == '#' or sections[0] == 'slabinfo':
                continue

            # name, num_objs, objsize
            self._slab_info.append([sections[0],
                                    int(sections[2]),
                                    int(sections[3])])

    @property
    def major_consumers(self):
        top5_name = {}
        top5_num_objs = {}
        top5_objsize = {}

        # /proc/slabinfo may not exist in containers/VMs
        if not os.path.exists(self.path):
            return

        for line in self.contents:
            name = line[0]
            # exclude kernel memory allocations
            if name.startswith('kmalloc'):
                continue

            num_objs = line[1]
            objsize = line[2]

            for i in range(5):
                if num_objs > top5_num_objs.get(i, 0):
                    top5_num_objs[i] = num_objs
                    top5_name[i] = name
                    top5_objsize[i] = objsize
                    break

        top5 = []
        for i in range(5):
            if top5_name.get(i):
                kbytes = top5_num_objs.get(i) * top5_objsize.get(i) / 1024
                top5.append("{} ({}k)".format(top5_name.get(i), kbytes))

        return top5


class BuddyInfo(object):

    def __init__(self):
        self._numa_nodes = []

    @property
    def path(self):
        return os.path.join(HotSOSConfig.DATA_ROOT, "proc/buddyinfo")

    @property
    def nodes(self):
        """Returns list of numa nodes."""
        # /proc/buddyinfo may not exist in containers/VMs
        if not os.path.exists(self.path):
            return self._numa_nodes

        if self._numa_nodes:
            return self._numa_nodes

        nodes = set()
        for line in open(self.path):
            nodes.add(int(line.split()[1].strip(',')))

        self._numa_nodes = list(nodes)
        return self._numa_nodes

    def get_node_zones(self, zones_type, node):
        for line in open(self.path):
            if line.split()[3] == zones_type and \
                    line.startswith("Node {},".format(node)):
                line = line.split()
                return " ".join(line)

        return None


class MallocInfo(object):

    def __init__(self, node, zone):
        self.node = node
        self.zone = zone
        self._block_sizes = {}

    @property
    def block_sizes_available(self):
        if self._block_sizes:
            return self._block_sizes

        node_zones = BuddyInfo().get_node_zones(self.zone, self.node)
        if node_zones is None:
            return

        # start from highest order zone (10) and work down to 0
        for order in range(10, -1, -1):
            free = int(node_zones.split()[5 + order - 1])
            self._block_sizes[order] = free

        return self._block_sizes

    @property
    def empty_order_tally(self):
        tally = 0
        for order, free in self.block_sizes_available.items():
            if not free:
                tally += order

        return tally

    @property
    def high_order_seq(self):
        """
        The number of contiguous available high-order block sizes.
        """
        available = self.block_sizes_available
        if not available:
            return 0

        # start from highest order zone (10) and work down to 0
        count = 0
        for blocks in sorted_dict(available, reverse=True).values():
            if blocks:
                break

            count += 1

        return count


class MemoryChecksResults(object):

    def __init__(self):
        self.results = {}

    def __len__(self):
        return len(self.results)

    def add(self, key, msg):
        self.results[key] = msg

    def __repr__(self):
        s = ""
        for k, v in self.results.items():
            if s:
                s += " "

            s += "{}: {}.".format(k, v)

        return s


class MemoryChecks(object):

    @property
    def max_unavailable_block_sizes(self):
        # 0+1+...10 is 55 so threshold is this minus the max order
        return 45

    @property
    def max_contiguous_unavailable_block_sizes(self):
        # this implies that top 5 orders are unavailable
        return 5

    @property
    def nodes_with_limited_high_order_memory(self):
        buddyinfo = BuddyInfo()
        nodes = []
        for zone in ['Normal', 'DMA32']:
            for node in buddyinfo.nodes:
                zone_info = MallocInfo(node, zone)
                if zone_info.high_order_seq:
                    if ((zone_info.empty_order_tally >=
                            self.max_unavailable_block_sizes) or
                        (zone_info.high_order_seq >
                            self.max_contiguous_unavailable_block_sizes)):
                        nodes.append("node{}-{}".format(node, zone.lower()))

        return nodes