import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from univpn_client.desktop import Bridge

class BridgeTest(unittest.TestCase):
    def test_cocoa_save_path_is_not_truncated_to_first_character(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'export.json';bridge=Bridge(directory)
            bridge._window=SimpleNamespace(create_file_dialog=lambda *a,**kw:str(path))
            webview=SimpleNamespace(FileDialog=SimpleNamespace(SAVE=1))
            with patch.dict('sys.modules',{'webview':webview}),patch('univpn_client.desktop.request',return_value='{"schema":1}'):
                self.assertEqual(bridge.export_file(),{'result':True})
            self.assertEqual(path.read_text(),'{"schema":1}')
    def test_no_window_filesystem_or_password_api_exposed(self):
        bridge=Bridge('/test/config')
        names={name for name in dir(bridge) if not name.startswith('_')}
        self.assertEqual(names,{'call','export_file','import_file','close_window'})
        self.assertEqual(bridge.call('get_password',{}),{'error':'Unknown action'})
        self.assertEqual(bridge.call('evaluate_js',{}),{'error':'Unknown action'})
    def test_valid_action_uses_shared_service(self):
        bridge=Bridge('/test/config')
        with patch('univpn_client.desktop.request',return_value={'version':'test'}) as call:
            self.assertEqual(bridge.call('snapshot',{}),{'result':{'version':'test'}})
            call.assert_called_once_with('snapshot',{},directory='/test/config')
