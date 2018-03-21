#!/usr/bin/env python
"""Zanata Server Helper functions"""

from __future__ import (
        absolute_import, division, print_function, unicode_literals)
import logging
import os
import os.path
import sys


from ZanataArgParser import ZanataArgParser
from ZanataFunctions import SshHost
from JenkinsHelper import JenkinsServer, JenkinsJob

try:
    # We need to import 'List' and 'Any' for mypy to work
    from typing import List, Any  # noqa: F401 # pylint: disable=unused-import
except ImportError:
    sys.stderr.write("python typing module is not installed" + os.linesep)


class ZanataServer(SshHost):
    """zanata.Server Class"""
    def __init__(
            self, host, ssh_user=None, identity=None,
            deploy_dir='/var/opt/rh/eap7/lib/wildfly/standalone/deployments'):
        # type (str, str, str) -> None
        """New an instance
        src_url: Source URL of zanata WAR file
        local_war_path: The local path to the WAR file"""
        super(ZanataServer, self).__init__(host, ssh_user, identity)
        self.deploy_dir = deploy_dir
        self.jboss_user = 'jboss'
        self.jboss_group = 'jboss'

    @classmethod
    def add_parser(cls, arg_parser=None):
        # type (ZanataArgParser) -> ZanataArgParser
        """Add Zanata Server parameters to a parser"""
        if not arg_parser:
            arg_parser = ZanataArgParser(description=__doc__)
        arg_parser = super(ZanataServer, cls).add_parser(arg_parser)
        # Include JenkinsJob parser for we need to download from jenkins
        if not arg_parser.has_common_argument(dest='branch'):
            arg_parser = JenkinsJob.add_parser(arg_parser, True)

        arg_parser.add_sub_command(
                'deploy-last-successful-war',
                None,
                help='Deploy last successful war from jenkins')
        return arg_parser

    @staticmethod
    def download_last_successful_war(
            jenkins_server, branch,
            folder, download_dir='/tmp'):
        # type (JenkinsServer, str, str) -> str
        """Dowload last successful war from jenkins"""
        logging.debug(
                "download_last_successful_war_from_jenkins(%s, %s, %s)",
                jenkins_server.server_url, branch, folder)
        jenkins_job = JenkinsJob(
                jenkins_server, 'zanata-platform', folder=folder,
                branch=branch)
        jenkins_job.load()
        war_file_list = jenkins_job.download_last_successful_artifacts(
                [r'zanata-war/.*/zanata.*\.war'],
                download_dir)
        return download_dir + '/' + os.path.basename(war_file_list[0])

    def scp_war_to_server(
            self, war_file, rm_old=True,
            scp_dest_dir='/usr/local/share/applications'):
        # type (str, bool, str) -> str
        """scp WAR file to server"""
        scp_dest_war = "%s/zanata.war" % scp_dest_dir
        self.scp_to_host(war_file, scp_dest_war, sudo=True, rm_old=rm_old)
        self.run_chown(self.jboss_user, self.jboss_group, scp_dest_war)
        return scp_dest_war

    def link_war_to_deploy_dir(self, scp_dest_war):
        # type (str) -> None
        """Stop eap, Link to War file, then Start eap"""
        logging.debug("link_war_to_deploy_dir(%s)", scp_dest_war)
        deploy_war_file = "%s/zanata.war" % self.deploy_dir
        self.run_check_call("systemctl stop eap7-standalone", True)
        self.run_check_call(
                "ln -sf %s %s" % (scp_dest_war, deploy_war_file), True)
        self.run_chown(self.jboss_user, self.jboss_group, deploy_war_file)
        self.run_check_call("systemctl start eap7-standalone", True)

    def deploy_last_successful_war(
            self, jenkins_server,
            branch='master',
            folder='github-zanata-org', rm_old=True):
        # type () -> None
        """Deploy the last successful war from jenkins"""
        downloaded_war = ZanataServer.download_last_successful_war(
                jenkins_server, branch, folder)
        scp_dest_war = self.scp_war_to_server(downloaded_war, rm_old)
        self.link_war_to_deploy_dir(scp_dest_war)
        logging.info("Done")


def run_sub_command(args):
    # type (dict) -> None
    """Run the sub command"""
    z_server = ZanataServer.init_from_parsed_args(args)
    if args.sub_command == 'deploy_last_successful_war':
        jenkins_server = JenkinsServer.init_from_parsed_args(args)
        kwargs = {}
        for key in ['branch', 'folder']:
            if hasattr(args, key) and getattr(args, key):
                kwargs[key] = getattr(args, key)
        z_server.deploy_last_successful_war(
                jenkins_server, **kwargs)


if __name__ == '__main__':
    run_sub_command(ZanataServer.add_parser().parse_all())
