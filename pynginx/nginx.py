import os
import subprocess
from pyparsing import Word, Literal, alphanums, OneOrMore, Optional, restOfLine, Group, NotAny

__author__ = 'vedran'


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
            configuration[file] = self._read_config_file(file_path, enabled)

        enabled_files = self._list_sites_enabled_files()

        for file in enabled_files:
            file_path = os.path.join(self.sites_enabled, file)
            enabled = True
            configuration[file] = self._read_config_file(file_path, enabled)

        self.configuration = configuration

    def get_server_by_name(self, name):
        sites_enabled_path = os.path.join(self.sites_enabled, name)
        sites_available_path = os.path.join(self.sites_available, name)

        if self.configuration and name in self.configuration.keys():
            return self.configuration[name]
        elif os.path.exists(sites_available_path):
            enabled = sites_available_path in self._list_sites_enabled_link_realpaths()
            return self._read_config_file(sites_available_path, enabled=enabled)
        elif os.path.exists(sites_enabled_path) and \
                not os.path.islink(sites_enabled_path):
            return self._read_config_file(sites_enabled_path, enabled=True)
        else:
            raise NginxConfigurationException('Configuration file \'%s\' not found in sites-available or '
                                              'sites-enabled' % name)

    def save_server(self, server, name):
        file_path = os.path.join(self.sites_available, name)
        try:
            existing_server = self.get_server_by_name(name)
            enabled = existing_server['enabled']
        except NginxConfigurationException:
            enabled = False

        with open(file_path, 'w') as f:
            f.write(str(server))
            server_conf = {'enabled': enabled, 'server': server, 'conf_file': file_path}
            if self.configuration:
                self.configuration[name] = server_conf
            return server_conf

    def enable_server(self, name):
        server = self.get_server_by_name(name)
        if not server['enabled']:
            os.symlink(server['conf_file'], os.path.join(self.sites_enabled, name))
            server['enabled'] = True

    def disable_server(self, name):
        server = self.get_server_by_name(name)
        if server['enabled']:
            sites_enabled_link = os.path.join(self.sites_enabled, name)
            if not os.path.islink(sites_enabled_link):
                raise NginxConfigurationException('Server configuration file %s is not a link. In order to disable '
                                                  'server configuration in a file, the configuration should be placed'
                                                  ' inside the sites-available directory, with link being placed in '
                                                  'sites-enabled')
            os.unlink(sites_enabled_link)
            server['enabled'] = False
        else:
            raise NginxConfigurationException('Server is already disabled')

    def reload(self):
        return subprocess.call([self.nginx_binary_path, "-s", 'reload'])

    def _read_config_file(self, file_path, enabled):
        with open(file_path) as f:
            return {'enabled': enabled, 'server': self.parser.parse(f.read()),
                    'conf_file': file_path}

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

