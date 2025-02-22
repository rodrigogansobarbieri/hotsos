import re

from hotsos.core.host_helpers import (
    APTPackageChecksBase,
    CLIHelper,
    ServiceChecksBase,
)
from hotsos.core.plugintools import PluginPartBase

PACEMAKER_PKGS_CORE = ['pacemaker', 'crmsh', 'corosync']
PACEMAKER_SVC_EXPR = ['pacemaker[a-zA-Z-]*',
                      'corosync']


class PacemakerBase(object):

    @property
    def crm_status(self):
        return CLIHelper().pacemaker_crm_status

    @property
    def offline_nodes(self):
        crm_status = self.crm_status()
        for line in crm_status:
            regex_match = re.search(r'.*OFFLINE.*\[\s(.*)\s\]',
                                    line)
            if regex_match:
                return regex_match.group(1).split()
        return []

    @property
    def online_nodes(self):
        crm_status = self.crm_status()
        for line in crm_status:
            regex_match = re.search(r'.*Online.*\[\s(.*)\s\]',
                                    line)
            if regex_match:
                return regex_match.group(1).split()
        return []


class PacemakerChecksBase(PacemakerBase, PluginPartBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apt = APTPackageChecksBase(core_pkgs=PACEMAKER_PKGS_CORE)
        self.systemd = ServiceChecksBase(service_exprs=PACEMAKER_SVC_EXPR)
        self.pacemaker = PacemakerBase()

    @property
    def apt_packages_all(self):
        return self.apt.all_formatted

    @property
    def plugin_runnable(self):
        return len(self.apt.core) > 0
