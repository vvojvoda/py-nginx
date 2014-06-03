import unittest
from pynginx.nginx import NginxManager, Server, Location, NginxConfigurationException, Parser
import os.path
from _pytest.monkeypatch import monkeypatch as mp
import subprocess


class NginxConfigurationTest(unittest.TestCase):

    def test_fail_if_no_configuration_file(self):
        def mockreturn_nginx_path(path):
            return False

        monkeypatch = mp()
        monkeypatch.setattr(os.path, 'exists', mockreturn_nginx_path)

        self.assertRaises(NginxConfigurationException, NginxManager, base_conf_location='/etc/nginx/')

    def test_config_file_exists(self):
        def mockreturn_nginx_path(path):
            return True

        def mockreturn_nginx_binary(subprocess):
            return '/usr/sbin/nginx'

        monkeypatch = mp()
        monkeypatch.setattr(os.path, 'exists', mockreturn_nginx_path)
        monkeypatch.setattr(subprocess, 'check_output', mockreturn_nginx_binary)

        man = NginxManager('/etc/nginx/')
        self.assertEqual('/etc/nginx/', man.conf_path)
        self.assertEqual('/usr/sbin/nginx', man.nginx_binary_path)

    def test_server_to_string(self):
        server = Server(port=1231, server_names=['example.com', 'example.net'],
                        params={'client_max_body_size': '20M',
                                'root': '/opt/mysite/',
                                'error_page': '500 502 /media/500.html'})

        location = Location('/media', params={'proxy_pass_header': 'Server',
                                              'proxy_set_header': 'Host $http_host',
                                              'proxy_redirect': 'off'})
        server.add_location(location=location)

        server_str = str(server)
        self.assertIn('location /media{', server_str)
        self.assertIn('client_max_body_size 20M;', server_str)
        self.assertIn('root /opt/mysite/;', server_str)
        self.assertIn('error_page 500 502 /media/500.html;', server_str)
        self.assertIn('1231;', server_str)
        self.assertIn('server_name example.com example.net;', server_str)

    def test_location_to_string(self):
        location = Location('/media', params={'proxy_pass_header': 'Server',
                                         'proxy_set_header': 'Host $http_host',
                                         'proxy_redirect': 'off'})

        location_str = str(location)
        self.assertIn('proxy_pass_header Server;', location_str)
        self.assertIn('proxy_set_header Host $http_host;', location_str)
        self.assertIn('proxy_redirect off;', location_str)
        self.assertIn('location /media{', location_str)

    def test_parser(self):
        with open('/Users/vedran/razvoj/python/usites/py-nginx/test/server_test.txt') as f:
            parser = Parser()
            print('*************')
            conf = f.read()
            print(conf, '->', parser.parse(conf))
            print('*************')
            self.fail()