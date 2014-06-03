import os
import subprocess
import tokenize

__author__ = 'vedran'

from pyparsing import Word, Literal, alphanums, printables, OneOrMore, Optional, restOfLine, ZeroOrMore, Group, NotAny
from pyparsing import LineStart, Dict, Combine


class Parser(object):
    server = Literal('server').suppress()
    location = Literal('location')
    semi = Literal(';').suppress()
    lbrace = Literal('{').suppress()
    rbrace = Literal('}').suppress()
    taraba = Literal('#')

    config_line = NotAny(rbrace) + Word(alphanums + '_') + Group(OneOrMore(Word(alphanums + '-' + '_' + '.' + '/' +
                                                                                '$' + ':'))) + semi
    location_def = location + Word(alphanums + '/' + '.') + lbrace + Group(OneOrMore(Group(config_line))) + rbrace
    server_def = server + lbrace + OneOrMore(Group(location_def) | Group(config_line)) + rbrace

    comment = taraba + Optional(restOfLine)
    server_def.ignore(comment)

    def parse(self, input_):
        parsed = self.server_def.parseString(input_)
        server_ = {}
        locations = []
        for part in parsed:
            k = part[0]
            if k.lower() == 'location':
                location_ = {'location': part[1]}
                locations.append(location_)
                for part2 in part[2]:
                    k2 = part2[0]
                    v2 = ' '.join(part2[1])
                    location_[k2] = v2
            else:
                v = ' '.join(part[1])
                server_[k] = v

        server = Server(port=int(server_.pop('listen')),
                        server_names=server_.pop('server_name').split(' '),
                        params=server_)
        for location_ in locations:
            location = Location(location=location_.pop('location'), params=location_)
            server.add_location(location)

        return server


class Server(object):
    def __init__(self, port, server_names, params):
        super(Server, self).__init__()
        self.port = port
        self.server_names = server_names
        self.locations = []
        self.params = params

    def add_location(self, location):
        self.locations.append(location)

    def __str__(self):
        rows = ['server{', 'listen %s;' % self.port]
        if self.server_names:
            rows.append('server_name %s;' % ' '.join(self.server_names))
        if 'root' in self.params:
            rows.append('root %s;' % self.params.pop('root'))

        for location in self.locations:
            rows.append(str(location))

        for k, v in self.params.items():
            rows.append('%s %s;' % (k, v))

        rows.append('}')
        return '\n'.join(rows)

    @staticmethod
    def parse(conf):
        raise NotImplemented()


class NginxManager(object):
    def __init__(self, base_conf_location):
        super(NginxManager, self).__init__()

        self.conf_path = base_conf_location
        self.nginx_conf_path = os.path.join(self.conf_path, 'nginx.conf')

        if not os.path.exists(self.nginx_conf_path):
            raise NginxConfigurationException('%s is not a valid nginx configuration root. nginx.conf file was not '
                                              'found at the specified location' % self.conf_path)

        if not os.path.exists(os.path.join(self.conf_path, 'sites-available')) or \
                not os.path.exists(os.path.join(self.conf_path, 'sites-enabled')):
            raise NginxConfigurationException('Nginx configuration root does not contain a \'sites-available\' '
                                              'or \'sites-enabled\' directory')

        #self.configuration = self._load()

        self.nginx_binary_path = None
        self._find_nginx_exec()

    def _load(self):
        """
        Loads all configuration files contained within {{conf_path}}/sites-available directory.

        :return: a dictionary where keys are the names of the files and values are server dictionaries in format:
        {"enabled": true/false, "server": Server}
        """
        sites_available = os.path.join(self.conf_path, 'sites-available')
        available_files = [f for f in os.listdir(sites_available) if os.path.isfile(os.path.join(sites_available, f))]

        sites_enabled = os.path.join(self.conf_path, 'sites-enabled')

        enabled_link_realpaths = [os.path.realpath(sites_enabled, f) for f in os.listdir(sites_enabled)
                                  if os.path.islink(os.path.join(sites_enabled, f))]

        configuration = {}
        for file in available_files:
            enabled = os.path.join(sites_available, file) in enabled_link_realpaths
            with open(file) as f:
                server = Server.parse(f)
                configuration[file] = {'enabled': enabled, 'server': server}

        enabled_files = [f for f in os.listdir(sites_enabled)
                         if os.path.isfile(os.path.join(sites_enabled, f))
                         and not os.path.islink(os.path.join(sites_enabled, f))]

        for file in enabled_files:
            enabled = True
            with open(file) as f:
                configuration[file] = {'enabled': enabled, 'server': Server.parse(f)}

        return configuration

    def _find_nginx_exec(self):
        try:
            output = subprocess.check_output(['which', 'nginx'])
            self.nginx_binary_path = output.rstrip()
        except subprocess.CalledProcessError:
            pass

    def add_server(self, virtual_host):
        pass


class Location(object):
    def __init__(self, location, params):
        super(Location, self).__init__()
        self.location = location
        self.params = params

    def __str__(self):
        rows = ['location %s{' % self.location]
        for k, v in self.params.items():
            rows.append('%s %s;' % (k, v))
        rows.append('}')
        return '\n'.join(rows)


class NginxConfigurationException(Exception):
    pass

