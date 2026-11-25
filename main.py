import threading
from waitress import serve
from kivy.app import App
from kivy.uix.widget import Widget
from kivy.clock import Clock
from android.runnable import run_on_ui_thread
from jnius import autoclass
import app as flask_app_module

def run_server():
    serve(flask_app_module.app, host='127.0.0.1', port=8080)

activity = autoclass('org.kivy.android.PythonActivity').mActivity
WebView = autoclass('android.webkit.WebView')
WebViewClient = autoclass('android.webkit.WebViewClient')

class AndroidApp(App):
    def build(self):
        threading.Thread(target=run_server, daemon=True).start()
        Clock.schedule_once(self.create_webview, 2)
        return Widget()

    @run_on_ui_thread
    def create_webview(self, dt):
        webview = WebView(activity)
        webview.getSettings().setJavaScriptEnabled(True)
        webview.getSettings().setDomStorageEnabled(True)
        webview.setWebViewClient(WebViewClient())
        webview.loadUrl("http://127.0.0.1:8080")
        activity.setContentView(webview)

if __name__ == '__main__':
    AndroidApp().run()
