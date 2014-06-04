import os
import subprocess
import tokenize

__author__ = 'vedran'

from pyparsing import Word, Literal, alphanums, OneOrMore, Optional, restOfLine, Group, NotAny


class ServerParser(object):
    def __init__(self):
        super(ServerParser, self).__init__()

        word = Word(alphanums + '-' + '_' + '.' + '/' + '$' + ':')
        server = Literal('server').suppress()
        location = Literal('location')
        lbrace = Literal('{').suppress()
        rbrace = Literal('}').suppress()

        config_line = NotAny(rbrace) + word + Group(OneOrMore(word)) + Literal(';').suppress()
        location_def = location + word + lbrace + Group(OneOrMore(Group(config_line))) + rbrace
        self.server_def = server + lbrace + OneOrMore(Group(location_def) | Group(config_line)) + rbrace

        comment = Literal('#') + Optional(restOfLine)
        self.server_def.ignore(comment)

    def parse(self, input_):
        parsed = self.server_def.parseString(input_)
        server_ = {}
        locations = []
        for part in parsed:
            k = part[0]
            if k.lower() == 'location':
                locations.append(self._build_location_dict(part))
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

    def _build_location_dict(self, parsed_location):
        location = {'location': parsed_location[1]}
        for part in parsed_location[2]:
            k = part[0]
            v = ' '.join(part[1])
            location[k] = v
        return location


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


class NginxManager(object):
    def __init__(self, base_conf_location):
        super(NginxManager, self).__init__()

        self.conf_path = base_conf_location
        self.nginx_conf_path = os.path.join(self.conf_path, 'nginx.conf')

        if not os.path.exists(self.nginx_conf_path):
            raise NginxConfigurationException('%s is not a valid nginx configuration root. nginx.conf file was not '
                                              'found at the specified location' % self.conf_path)

        self.sites_available = os.path.join(self.conf_path, 'sites-available')
        self.sites_enabled = os.path.join(self.conf_path, 'sites-enabled')

        if not os.path.exists(self.sites_available) or not os.path.exists(self.sites_enabled):
            raise NginxConfigurationException('Nginx configuration root does not contain a \'sites-available\' '
                                              'or \'sites-enabled\' directory')

        self.configuration = None

        self.nginx_binary_path = None
        self._find_nginx_exec()
        self.parser = ServerParser()

    def load(self):
        """
        Loads all configuration files contained within {{conf_path}}/sites-available directory.

        File are loaded into a dictionary where keys are the names of the files and values are server dictionaries in
        format: {"enabled": true/false, "server": Server}
        """
        available_files = self._list_sites_available()
        enabled_link_realpaths = self._list_sites_enabled_link_realpaths()

        configuration = {}
        for file in available_files:
            file_path = os.path.join(self.sites_available, file)
            enabled = file_path in enabled_link_realpaths
            with open(file_path) as f:
                server = self.parser.parse(f.read())
                configuration[file] = {'enabled': enabled, 'server': server,
                                       'conf_file': file_path}

        enabled_files = self._list_sites_enabled_files()

        for file in enabled_files:
            file_path = os.path.join(self.sites_enabled, file)
            enabled = True
            with open(file_path) as f:
                configuration[file] = {'enabled': enabled, 'server': self.parser.parse(f.read()),
                                       'conf_file': file_path}

        self.configuration = configuration

    def _find_nginx_exec(self):
        try:
            output = subprocess.check_output(['which', 'nginx'])
            self.nginx_binary_path = output.rstrip()
        except subprocess.CalledProcessError:
            pass

    def _list_sites_available(self):
        return [f for f in os.listdir(self.sites_available) if os.path.isfile(os.path.join(self.sites_available, f))]

    def _list_sites_enabled_link_realpaths(self):
        return [os.path.realpath(self.sites_enabled, f) for f in os.listdir(self.sites_enabled)
                if os.path.islink(os.path.join(self.sites_enabled, f))]

    def _list_sites_enabled_files(self):
        return [f for f in os.listdir(self.sites_enabled)
                if os.path.isfile(os.path.join(self.sites_enabled, f))
                and not os.path.islink(os.path.join(self.sites_enabled, f))]

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

