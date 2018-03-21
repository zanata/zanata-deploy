#!/usr/bin/env python
"""ZanataArgParser is an sub-class of ArgumentParser
that handles sub-parser, environments more easily."""

from __future__ import (
        absolute_import, division, print_function, unicode_literals)

from argparse import ArgumentParser, ArgumentError
import logging
import os
import re


class ZanataArgParser(ArgumentParser):
    """Zanata Argument Parser"""
    def __init__(self, *args, **kwargs):
        # type: (str, object, object) -> None
        super(ZanataArgParser, self).__init__(*args, **kwargs)
        self.sub_parsers = None
        self.env_def = {}
        self.parent_parser = ArgumentParser(add_help=False)
        self.parent_parser.add_argument(
                '-v', '--verbose', type=str, default='INFO',
                metavar='VERBOSE_LEVEL',
                help='Valid values: %s'
                % 'DEBUG, INFO, WARNING, ERROR, CRITICAL, NONE')

    def add_common_argument(self, *args, **kwargs):
        # type:  (str, object, object) -> argparse
        """Add a common argument that will be used in all sub commands
        In other words, common argument wil be put in common parser.
        Note that add_common_argument must be put in then front of
        add_sub_command that uses common arguments."""
        self.parent_parser.add_argument(*args, **kwargs)

    def add_sub_command(self, name, arguments, **kwargs):
        # type:  (str, object, object) -> argparse ArgumentParser
        """Add a sub command"""
        if not self.sub_parsers:
            self.sub_parsers = self.add_subparsers(
                    title='Command', description='Valid commands',
                    help='Command help')
        sub_command_name = re.sub('-', '_', name)

        if self.parent_parser:
            # common argument aleady defined
            if 'parents' in kwargs:
                kwargs['parents'] += [self.parent_parser]
            else:
                kwargs['parents'] = [self.parent_parser]
        anonymous_parser = self.sub_parsers.add_parser(
                name, **kwargs)
        if arguments:
            for k, v in arguments.iteritems():
                anonymous_parser.add_argument(*k.split(), **v)
        anonymous_parser.set_defaults(sub_command=sub_command_name)
        return anonymous_parser

    def add_env(  # pylint: disable=too-many-arguments
            self, env_name,
            default=None,
            required=False,
            value_type=str,
            dest=''):
        # type: (str, object, bool, type) -> None
        """Add environment variable"""
        if not dest:
            dest = env_name.lower()
        if env_name in self.env_def:
            raise ArgumentError(
                    None, "Duplicate environment name %s" % env_name)
        self.env_def[env_name] = {
                'default': default,
                'required': required,
                'value_type': value_type,
                'dest': dest}

    def has_common_argument(self, option_string=None, dest=None):
        # type: (str, str) -> bool
        """Whether this parser parses this common argument"""
        for action in self.parent_parser._actions:  # pylint: disable=W0212
            if option_string:
                if option_string in action.option_strings:
                    return True
                else:
                    continue
            elif dest:
                if dest == action.dest:
                    return True
                else:
                    continue
            else:
                raise ArgumentError(None, "need either option_string or dest")
        return False

    def has_env(self, env_name):
        # type: (str) -> bool
        """Whether this parser parses this environment"""
        return env_name in self.env_def

    def parse_args(self, args=None, namespace=None):
        # type: (str, List, object) -> argparse.Namespace
        """Parse arguments"""
        result = super(ZanataArgParser, self).parse_args(args, namespace)
        logging.basicConfig(
                format='%(asctime)-15s [%(levelname)s] %(message)s')
        logger = logging.getLogger()
        if result.verbose == 'NONE':
            # Not showing any log
            logger.setLevel(logging.CRITICAL + 1)
        elif hasattr(logging, result.verbose):
            logger.setLevel(getattr(logging, result.verbose))
        else:
            ArgumentError(None, "Invalid verbose level: %s" % result.verbose)
        delattr(result, 'verbose')
        return result

    def parse_env(self):
        # type: () -> dict
        """Parse environment"""
        result = {}
        for env_name, env_data in self.env_def.iteritems():
            env_value = os.environ.get(env_name)
            if not env_value:
                if env_data['required']:
                    raise AssertionError("Missing environment '%s'" % env_name)
                elif not env_data['default']:
                    continue
                else:
                    env_value = env_data['default']
            result[env_data['dest']] = env_value
        return result

    def parse_all(self, args=None, namespace=None):
        # type: (str, List, object) -> argparse.Namespace
        """Parse arguments and environment"""
        result = self.parse_args(args, namespace)
        env_dict = self.parse_env()
        for k, v in env_dict.iteritems():
            setattr(result, k, v)
        return result
