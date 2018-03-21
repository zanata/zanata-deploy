#!/usr/bin/env python
"""Zanata WAR Helper functions"""

import argparse
import os
import sys
import urlparse  # pylint: disable=import-error
# python3-pylint does not do well on importing python2 module
from ZanataFunctions import logging_init
from ZanataFunctions import SshHost
from ZanataFunctions import UrlHelper
import JenkinsHelper

try:
    # We need to import 'List' and 'Any' for mypy to work
    from typing import List, Any  # noqa: F401 # pylint: disable=unused-import
except ImportError:
    sys.stderr.write("python typing module is not installed" + os.linesep)


class ZanataWar(object):
    """Class that manipulate zanata.war"""
    def __init__(self, download_url=None, local_path=None):
        # type (str, str) -> None
        self.download_url = download_url
        self.local_path = local_path

    def __getitem__(self, key):
        # type: (str) -> str
        return self[key]

    @staticmethod
    def create_parent_parser():
        # type () -> argparse.ArgumentParser
        """Create a parser as parent of Zanata war argument parser"""
        parent_parser = argparse.ArgumentParser(add_help=False)
        parent_parser.add_argument(
                '-l', '--local-path', type=str,
                help='Path to local WAR file.')
        return parent_parser

    @staticmethod
    def get_last_successful_build_url(server, job_name, folder, branch):
        # type (JenkinsHelper.JenkinsServer, str, str, str) -> str
        """Get the WAR file download url for last successful build"""
        job = JenkinsHelper.JenkinsJob(server, job_name, folder, branch)
        job.load()
        build = job.get_last_successful_build()
        build.load()
        war_paths = build.list_artifacts_related_paths(
                r'^.*/zanata-([0-9.]+).*\.war$')
        return build.url + 'artifact/' + war_paths[0]

    def download(
            self,
            dest_file=None,
            dest_dir=None):
        # type (str, str) -> None
        """Download WAR file from .download_url"""
        if not self.download_url:
            raise AssertionError("war download_url is not set.")
        target_file = dest_file
        if not target_file:
            url_dict = urlparse.urlparse(self.download_url)
            target_file = os.path.basename(url_dict.path)

        target_dir = os.path.abspath('.' if not dest_dir else dest_dir)
        UrlHelper.download_file(self.download_url, target_file, target_dir)
        self.local_path = os.path.join(target_dir, target_file)

    def scp_to_server(  # pylint: disable=too-many-arguments
            self, dest_host,
            dest_path=None,
            identity_file=None,
            rm_old=False,
            chmod=False,
            source_path=None):
        # type (str, str, str, bool, bool, str) -> None
        """SCP to Zanata server"""
        local_path = source_path if source_path else self.local_path
        if not local_path:
            raise AssertionError("source_path is missing")
        if not os.path.isfile(local_path):
            raise AssertionError(local_path + " does not exist")

        if dest_path:
            target_path = dest_path
        else:
            target_path = (
                    '/var/opt/rh/eap7/lib/wildfly/standalone/deployments/'
                    'zanata.war')

        ssh_host = SshHost(dest_host, identity_file)
        ssh_host.scp_to_remote(local_path, target_path, True, rm_old)

        if chmod:
            ssh_host.run_check_call(
                    "chown jboss:jboss %s" % target_path, True)


def show_download_link():
    # type () -> None
    """Show the download link of last successful build"""
    server = JenkinsHelper.JenkinsServer.init_default()

    war = ZanataWar(ZanataWar.get_last_successful_build_url(
            server, args.job, args.folder, args.branch))
    print(war.download_url)


def download_from_jenkins():
    # type () -> None
    """Handling download-from-jenkins command
    (download last successful build)"""
    server = JenkinsHelper.JenkinsServer.init_default()

    war = ZanataWar(ZanataWar.get_last_successful_build_url(
            server, args.job, args.folder, args.branch))
    war.download(
            None if not args.local_path else os.path.basename(args.local_path),
            None if not args.local_path else os.path.dirname(args.local_path))


def scp_to_server():
    # type () -> None
    """Handling scp-to-server command"""
    server = JenkinsHelper.JenkinsServer.init_default()

    war = ZanataWar(
            ZanataWar.get_last_successful_build_url(
                    server, args.job, args.folder, args.branch),
            args.local_path)

    war.scp_to_server(args.host, args.dest_path, args.identity_file)


def deploy_local_war(war=None):
    # type () -> None
    """Deploy a build local WAR to zanata server.
    This assumes login as root"""
    if not war:
        if not args.war_file:
            raise AssertionError("args.war_file is missing")
        war = ZanataWar(local_path=args.war_file)

    ssh_host = SshHost(args.host, args.identity_file)
    ssh_host.run_check_call("systemctl stop eap7-standalone", True)
    war.scp_to_server(
            args.host, args.dest_path, args.identity_file,
            True, True)

    ssh_host.run_check_call("systemctl start eap7-standalone", True)


def deploy():
    # type () -> None
    """Download the last successfully built WAR, then deploy
    the WAR file to zanata server.
    This assumes login as root"""
    server = JenkinsHelper.JenkinsServer.init_default()

    war = ZanataWar(
            ZanataWar.get_last_successful_build_url(
                    server, args.job, args.folder, args.branch),
            args.local_path)

    war.download(
            None if not args.local_path else os.path.basename(args.local_path),
            None if not args.local_path else os.path.dirname(args.local_path))

    deploy_local_war(war)


def parse():
    # type () -> None
    """Parse options and arguments"""
    parser = argparse.ArgumentParser(description='WAR file functions')
    job_parent_parser = JenkinsHelper.JenkinsServer.create_parent_parser()
    war_parent_parser = ZanataWar.create_parent_parser()
    ssh_parent_parser = SshHost.create_parent_parser()

    subparsers = parser.add_subparsers(
            title='Command', description='Valid commands',
            help='Command help')

    show_download_link_parser = subparsers.add_parser(
            'show-download-link',
            help='Show download link',
            parents=[job_parent_parser, war_parent_parser])
    show_download_link_parser.set_defaults(func=show_download_link)

    download_from_jenkins_parser = subparsers.add_parser(
            'download-from-jenkins',
            help='Download from jenkins',
            parents=[job_parent_parser, war_parent_parser])
    download_from_jenkins_parser.set_defaults(func=download_from_jenkins)

    scp_to_server_parser = subparsers.add_parser(
            'scp-to-server',
            help='scp to server',
            parents=[job_parent_parser, war_parent_parser, ssh_parent_parser])
    scp_to_server_parser.set_defaults(func=scp_to_server)

    deploy_local_war_parser = subparsers.add_parser(
            'deploy-local-war',
            help="""deploy the existing local WAR to server
            (assuming you are able to sudo)""",
            parents=[ssh_parent_parser])
    deploy_local_war_parser.add_argument(
            'war_file', type=str,
            help='Local WAR file to be upload')
    deploy_local_war_parser.set_defaults(func=deploy_local_war)

    deploy_parser = subparsers.add_parser(
            'deploy',
            help="""deploy the last successful built WAR to server
            (assuming you are able to sudo)""",
            parents=[job_parent_parser, war_parent_parser, ssh_parent_parser])
    deploy_parser.set_defaults(func=deploy)
    return parser.parse_args()


if __name__ == '__main__':
    # Set logging
    logging_init()

    args = parse()  # pylint: disable=invalid-name
    args.func()
