#!/usr/bin/env python
"""Jenkins Helper functions
It contains jenkins helper
Run JenkinsHelper --help or JenkinsHelper --help <command> for
detail help."""

import argparse
import ast
import logging
import os
import os.path
import re
import sys

# from typing import List, Any    # noqa: F401 # pylint: disable=unused-import
from ZanataFunctions import UrlHelper, logging_init

try:
    # We need to import 'List' and 'Any' for mypy to work
    from typing import List, Any  # noqa: F401 # pylint: disable=unused-import
except ImportError:
    sys.stderr.write("python typing module is not installed" + os.linesep)


class JenkinsServer(object):
    """Jenkins Helper functions"""
    def __init__(self, server_url, user, token):
        # type: (str, str,str) -> None
        self.url_helper = UrlHelper(
                server_url, user, token)
        self.server_url = server_url
        self.user = user
        self.token = token

    def __getitem__(self, key):
        # type: (str) -> str
        return self[key]

    @staticmethod
    def init_default():
        # type: () -> None
        """Init JenkinsServer connection with default environment."""
        zanata_jenkins = {
                'server_url': os.environ.get('JENKINS_URL'),
                'user': os.environ.get('ZANATA_JENKINS_USER'),
                'token': os.environ.get('ZANATA_JENKINS_TOKEN'),
                }

        if not zanata_jenkins['server_url']:
            raise AssertionError("Missing environment 'JENKINS_URL'")
        if not zanata_jenkins['user']:
            raise AssertionError("Missing environment 'ZANATA_JENKINS_USER'")
        if not zanata_jenkins['token']:
            raise AssertionError("Missing environment 'ZANATA_JENKINS_TOKEN'")

        return JenkinsServer(
                zanata_jenkins['server_url'],
                zanata_jenkins['user'],
                zanata_jenkins['token'],
                )

    @staticmethod
    def create_parent_parser():
        # type () -> argparse.ArgumentParser
        """Create a parser as parent of Jenkins job argument parser
        e.g. -F <folder>, -b <branch> and <job>"""
        job_parent_parser = argparse.ArgumentParser(add_help=False)
        job_parent_parser.add_argument(
                '-F', '--folder', type=str, default='',
                help='folder name')
        job_parent_parser.add_argument(
                '-b', '--branch', type=str, default='',
                help='branch or PR name')
        job_parent_parser.add_argument('job', type=str, help='job name')
        return job_parent_parser


class JenkinsJob(object):
    """Jenkins Job Objects"""

    @staticmethod
    def dict_get_elem_by_path(dic, path):
        # type (dict, str) -> object
        """Return the elem in python dictionary given path
        for example: you can use a/b to retrieve answer from following
        dict:
            { 'a': { 'b': 'answer' }}"""
        obj = dic
        for key in path.split('/'):
            if obj[key]:
                obj = obj[key]
            else:
                return None
        return obj

    @staticmethod
    def print_key_value(key, value):
        # type (str, str) -> None
        """Pretty print the key and value"""
        return "%30s : %s" % (key, value)

    def get_elem(self, path):
        # type: (str) -> object
        """Get element from the job object"""
        return JenkinsJob.dict_get_elem_by_path(self.content, path)

    def __repr__(self):
        # type: () -> str
        result = "\n".join([
                JenkinsJob.print_key_value(tup[0], tup[1]) for tup in [
                        ['name', self.name],
                        ['folder', self.folder],
                        ['branch', self.branch]]])
        if self.content:
            result += "\n\n%s" % "\n".join([
                    JenkinsJob.print_key_value(
                            key, self.get_elem(key)) for key in [
                                    'displayName',
                                    'fullName',
                                    'lastBuild/number',
                                    'lastCompletedBuild/number',
                                    'lastFailedBuild/number',
                                    'lastSuccessfulBuild/number']])
        return result

    def __init__(self, server, name, folder, branch):
        # type (JenkinsServer, str, str, str) -> None
        self.server = server
        self.name = name
        self.folder = folder
        self.branch = branch
        self.content = None
        job_path = "job/%s" % self.name
        if folder:
            job_path = "job/%s/%s" % (folder, job_path)
        if branch:
            job_path += "/job/%s" % branch
        self.url = "%s%s" % (self.server.server_url, job_path)

    def __getitem__(self, key):
        # type: (str) -> str
        return self[key]

    def load(self):
        # type: () -> None
        """Load the build object from Jenkins server"""
        logging.info("Loading job from %s/api/python", self.url)
        self.content = ast.literal_eval(UrlHelper.read(
                "%s/api/python" % self.url))

    def get_last_successful_build(self):
        # type: () -> JenkinsJobBuild
        """Get last successful build"""
        if not self.content:
            self.load()

        if not self.content:
            raise AssertionError("Failed to load job from %s" % self.url)
        return JenkinsJobBuild(
                self,
                int(self.get_elem('lastSuccessfulBuild/number')),
                self.get_elem('lastSuccessfulBuild/url'))


class JenkinsJobBuild(object):
    """Build object for Jenkins job"""

    def __init__(self, parent_job, build_number, build_url):
        # type (object, int, str) -> None
        self.parent_job = parent_job
        self.number = build_number
        self.url = build_url
        self.content = None

    def __getitem__(self, key):
        # type: (str) -> str
        return self[key]

    def get_elem(self, path):
        # type: (str) -> object
        """Get element from the build object"""
        return JenkinsJob.dict_get_elem_by_path(self.content, path)

    def load(self):
        """Load the build object from Jenkins server"""
        logging.info("Loading build from %sapi/python", self.url)
        self.content = ast.literal_eval(UrlHelper.read(
                "%s/api/python" % self.url))

    def list_artifacts_related_paths(self, artifact_path_pattern='.*'):
        # type: (str) -> List[str]
        """Return a List of relativePaths of artifacts
        that matches the path pattern"""
        if not self.content:
            self.load()
        if not self.content:
            raise AssertionError("Failed to load build from %s" % self.url)
        return [
                artifact['relativePath']
                for artifact in self.content['artifacts']
                if re.search(artifact_path_pattern, artifact['relativePath'])]

    def __repr__(self):
        # type: () -> str
        result = "\n".join([
                JenkinsJob.print_key_value(
                        tup[0], str(tup[1])) for tup in [
                                ['number', self.number],
                                ['url', self.url]]])

        if self.content:
            result += "\n\n%s" % "\n".join([
                    JenkinsJob.print_key_value(
                            key, self.get_elem(key)) for key in [
                                    'nextBuild/number',
                                    'previousBuild/number']])
            result += "\n\nArtifacts:\n%s" % "\n  ".join(
                    self.list_artifacts_related_paths())
        return result


def show_job():
    # type () -> None
    """Show the job information"""
    server = JenkinsServer.init_default()
    job = JenkinsJob(server, args.job, args.folder, args.branch)
    print(job)


def show_last_successful_build():
    # type () -> None
    """Show the last successful build for a Jenkins job"""
    server = JenkinsServer.init_default()
    job = JenkinsJob(server, args.job, args.folder, args.branch)

    build = job.get_last_successful_build()
    build.load()
    print(build)


def parse():
    # type () -> None
    """Parse options and arguments"""

    parser = argparse.ArgumentParser(description='Jenkins helper functions')
    job_parent_parser = JenkinsServer.create_parent_parser()

    subparsers = parser.add_subparsers(
            title='Command', description='Valid commands',
            help='Command help')

    job_parser = subparsers.add_parser(
            'show-job',
            help='Get Job objects',
            parents=[job_parent_parser],
            )
    job_parser.set_defaults(func=show_job)

    build_parser = subparsers.add_parser(
            'show-last-successful-build',
            help='Get build objects',
            parents=[job_parent_parser])
    build_parser.set_defaults(func=show_last_successful_build)

    return parser.parse_args()


if __name__ == '__main__':
    logging_init()

    args = parse()  # pylint: disable=invalid-name
    args.func()
