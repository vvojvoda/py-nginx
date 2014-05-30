import os
import subprocess

__author__ = 'vedran'


class NginxManager(object):

    def __init__(self, base_conf_location):
        super(NginxManager, self).__init__()

        self.conf_path = base_conf_location
        self.nginx_conf_path = os.path.join(self.conf_path, 'nginx.conf')

        if not os.path.exists(self.nginx_conf_path):
            raise NginxConfigurationException('%s is not a valid nginx configuration root. nginx.conf file was not '
                                              'found at the specified location' % self.conf_path)

        if not os.path.exists(os.path.join(self.conf_path, 'sites-available')):
            raise NginxConfigurationException('Nginx configuration root does not contain a \'sites-available\' '
                                              'directory')

        self.nginx_binary_path = None
        self._find_nginx_exec()

    def _find_nginx_exec(self):
        try:
            output = subprocess.check_output(['which', 'nginx'])
            self.nginx_binary_path = output.rstrip()
        except subprocess.CalledProcessError:
            pass

    def add_server(self, virtual_host):
        pass


class Server(object):

    def __init__(self, port, server_names, **kwargs):
        super(Server, self).__init__()
        self.port = port
        self.server_names = server_names
        self.locations = []
        self.params = kwargs

    def add_location(self, location):
        self.locations = location

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

