from hotsos.core.log import log
from hotsos.core.searchtools import SearchDef
from hotsos.core.plugins.kernel.kernlog.common import KernLogBase


class OverMTUDroppedPacketEvent(object):

    @property
    def searchdef(self):
        return SearchDef(r'.+\] (\S+): dropped over-mtu packet',
                         hint='dropped', tag='over-mtu-dropped')


class KernLogEvents(KernLogBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for event in [OverMTUDroppedPacketEvent()]:
            self.searcher.add_search_term(event.searchdef, self.path)

        self.results = self.searcher.search()

    @property
    def over_mtu_dropped_packets(self):
        interfaces = {}
        for r in self.results.find_by_tag('over-mtu-dropped'):
            if r.get(1) in interfaces:
                interfaces[r.get(1)] += 1
            else:
                interfaces[r.get(1)] = 1

        if interfaces:
            # only report on interfaces that currently exist
            host_interfaces = [iface.name for iface in
                               self.hostnet_helper.host_interfaces_all]
            # filter out interfaces that are actually ovs bridge aliases
            ovs_bridges = self.cli_helper.ovs_vsctl_list_br()
            # strip trailing newline chars
            ovs_bridges = [br.strip() for br in ovs_bridges]

            interfaces_extant = {}
            for iface in interfaces:
                if iface in host_interfaces:
                    if iface not in ovs_bridges:
                        interfaces_extant[iface] = interfaces[iface]
                    else:
                        log.debug("excluding ovs bridge %s", iface)

            if interfaces_extant:
                # sort by number of occurrences
                sorted_dict = {}
                for k, v in sorted(interfaces_extant.items(),
                                   key=lambda e: e[1], reverse=True):
                    sorted_dict[k] = v

                return sorted_dict
