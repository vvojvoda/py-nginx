import unittest
from pynginx.nginx import NginxManager, Server, Location, NginxConfigurationException, ServerParser
import os.path
from _pytest.monkeypatch import monkeypatch as mp
import subprocess


class NginxConfigurationTest(unittest.TestCase):
    test_files_dir = os.path.join(os.path.dirname(__file__), 'files')

    def setUp(self):
        self.monkeypatch = mp()

    def tearDown(self):
        self.monkeypatch.undo()

    def _mock_sites_directories(self, manager):
        self.monkeypatch.setattr(manager, 'sites_available', os.path.join(self.test_files_dir, 'available'))
        self.monkeypatch.setattr(manager, 'sites_enabled', os.path.join(self.test_files_dir, 'enabled'))

    def _make_manager_init_pass(self):
        def mockreturn_nginx_path(path):
            return True

        def mockreturn_nginx_binary(subprocess):
            return '/argh/mrmr/giberish'

        self.monkeypatch.setattr(os.path, 'exists', mockreturn_nginx_path)
        self.monkeypatch.setattr(subprocess, 'check_output', mockreturn_nginx_binary)

    def test_fail_if_no_configuration_file(self):
        def mockreturn_nginx_path(path):
            return False

        self.monkeypatch.setattr(os.path, 'exists', mockreturn_nginx_path)

        self.assertRaises(NginxConfigurationException, NginxManager, base_conf_location='/etc/nginx/')

    def test_config_file_exists(self):
        self._make_manager_init_pass()

        man = NginxManager('/etc/nginx/')
        self.assertEqual('/etc/nginx/', man.conf_path)

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
        with open(os.path.join(self.test_files_dir, 'available', 'server')) as f:
            parser = ServerParser()
            conf = f.read()
            server = parser.parse(conf)
            self.assertEqual(80, server.port)
            self.assertIn('example.com', server.server_names)
            self.assertEqual(6, len(server.locations))
            location = [x for x in server.locations if x.location == '/robots.txt'][0]
            self.assertIn('allow', location.params)
            self.assertIn('/opt/example/robots.txt', location.params.get('alias'))

    def test_get_server_by_name(self):
        self._make_manager_init_pass()
        man = NginxManager('/etc/nginx')

        #Revert the monkeypatch making os.path.exists always return True
        self.monkeypatch.undo()
        self._mock_sites_directories(man)

        server = man.get_server_by_name(name='server')
        self.assertFalse(server['enabled'])

        server = man.get_server_by_name(name='server2')
        self.assertTrue(server['enabled'])

        self.assertRaises(NginxConfigurationException, man.get_server_by_name, name='nonexists')

        man.load()
        server = man.get_server_by_name(name='server')
        self.assertFalse(server['enabled'])
        self.assertEqual(80, server['server'].port)

    def test_save_enable_disable_server(self):

        def mockreturn_realpaths():
            return [os.path.join(self.test_files_dir, 'available', 'new_server')]

        try:
            server = Server(port=80, server_names=['example2.com'], params={'root': '/opt/example2/'})
            self._make_manager_init_pass()
            man = NginxManager('/etc/nginx')
            self.monkeypatch.undo()
            self._mock_sites_directories(man)
            man.save_server(server, 'new_server')

            new_file_path = os.path.join(man.sites_available, 'new_server')
            new_file_link_path = os.path.join(man.sites_enabled, 'new_server')
            self.assertTrue(os.path.exists(new_file_path))

            #make the parser pass on this new file
            parser = ServerParser()
            with open(new_file_path) as f:
                parser.parse(f.read())

            self.assertFalse(os.path.exists(new_file_link_path))
            man.enable_server('new_server')
            self.assertTrue(os.path.exists(new_file_link_path))
            self.assertTrue(os.path.islink(new_file_link_path))
            self.monkeypatch.setattr(man, '_list_sites_enabled_link_realpaths', mockreturn_realpaths)
            man.disable_server('new_server')
            self.assertFalse(os.path.exists(new_file_link_path))

        finally:
            if os.path.exists(new_file_link_path):
                os.unlink(new_file_link_path)
            if os.path.exists(new_file_path):
                os.remove(new_file_path)

    def test_load_configuration(self):

        def mockreturn_realpaths():
            return [os.path.join(self.test_files_dir, 'available', 'server')]

        self._make_manager_init_pass()
        man = NginxManager('/etc/nginx/')

        self._mock_sites_directories(man)
        man.load()
        self.assertIsNotNone(man.configuration)
        self.assertEqual(False, man.configuration['server']['enabled'])
        self.assertEqual(80, man.configuration['server']['server'].port)

        self.monkeypatch.setattr(man, '_list_sites_enabled_link_realpaths', mockreturn_realpaths)
        man.load()
        self.assertEqual(True, man.configuration['server']['enabled'])

        self.assertEqual(2, len(man.configuration.keys()))
        self.assertEqual(True, man.configuration['server2']['enabled'])