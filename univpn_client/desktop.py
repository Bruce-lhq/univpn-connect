"""Trusted local UI with a narrow bridge; no password-reading API."""
from pathlib import Path
import sys
from .service import ensure_service,request


class Bridge:
    def __init__(self,directory=None):self._directory=directory;self._window=None
    def call(self,method,params):
        from .daemon import API
        if method not in API.METHODS:return {'error':'Unknown action'}
        try:return {'result':request(method,params,directory=self._directory)}
        except Exception as exc:return {'error':str(exc)}
    def export_file(self):
        import webview
        try:
            files=self._window.create_file_dialog(webview.FileDialog.SAVE,save_filename='univpn-config.json',file_types=('JSON (*.json)',))
            if not files:return {'result':False}
            # Cocoa SAVE returns a string in pywebview 6; OPEN returns a tuple.
            path=Path(files if isinstance(files,str) else files[0])
            path.write_text(request('export_config',directory=self._directory),encoding='utf-8')
            return {'result':True}
        except Exception as exc:return {'error':str(exc)}
    def import_file(self):
        import webview
        try:
            files=self._window.create_file_dialog(webview.FileDialog.OPEN,allow_multiple=False,file_types=('JSON (*.json)',))
            if not files:return {'result':False}
            path=Path(files[0])
            if path.stat().st_size>1024*1024:raise ValueError('Configuration file is too large')
            request('import_config',{'text':path.read_text(encoding='utf-8')},directory=self._directory)
            return {'result':True}
        except Exception as exc:return {'error':str(exc)}
    def close_window(self):self._window.destroy()


def main(directory=None):
    import webview
    ensure_service(directory)
    root=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))
    bridge=Bridge(directory)
    bridge._window=webview.create_window('UniVPN Connect',url=str(root/'ui'/'index.html'),
                                       js_api=bridge,width=940,height=690,min_size=(680,520))
    webview.start(private_mode=True)
    return 0
