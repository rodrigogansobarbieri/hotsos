from hotsos.core.plugintools import summary_entry_offset as idx
from hotsos.core.plugins.vault import VaultChecksBase


class VaultSummary(VaultChecksBase):

    @idx(0)
    def __summary_services(self):
        if self.systemd.services:
            return {'systemd': self.systemd.service_info,
                    'ps': self.systemd.process_info}

    @idx(1)
    def __summary_snaps(self):
        if self.snaps.core:
            return self.snaps.all_formatted
