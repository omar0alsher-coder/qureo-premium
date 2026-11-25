package com.qureo.solver;

import android.annotation.SuppressLint;
import android.app.NotificationManager;
import android.content.Intent;
import android.os.Build;
import android.os.Bundle;
import android.webkit.JavascriptInterface;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.webkit.WebChromeClient;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.app.NotificationCompat;
import androidx.core.view.WindowCompat;
import androidx.core.view.WindowInsetsCompat;
import androidx.core.view.WindowInsetsControllerCompat;

import okhttp3.*;
import java.io.IOException;

public class MainActivity extends AppCompatActivity {
    private WebView webView;
    private OkHttpClient client = new OkHttpClient();
    private String cookieStr = "";

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        
        // إخفاء الخط الأسود (Full Screen)
        WindowCompat.setDecorFitsSystemWindows(getWindow(), false);
        WindowInsetsControllerCompat controller = new WindowInsetsControllerCompat(getWindow(), getWindow().getDecorView());
        controller.hide(WindowInsetsCompat.Type.systemBars());
        controller.setSystemBarsBehavior(WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);

        // تشغيل خدمة الخلفية
        startService(new Intent(this, KeepAliveService.class));

        webView = new WebView(this);
        setContentView(webView);

        webView.getSettings().setJavaScriptEnabled(true);
        webView.getSettings().setDomStorageEnabled(true);
        webView.getSettings().setAllowFileAccess(true);
        webView.getSettings().setAllowContentAccess(true);
        webView.getSettings().setAllowUniversalAccessFromFileURLs(true);
        webView.getSettings().setAllowFileAccessFromFileURLs(true);

        webView.setWebViewClient(new WebViewClient());
        webView.setWebChromeClient(new WebChromeClient());

        // الجسر بين HTML والجافا عشان نبعت الطلبات بسرعة بدون CORS
        webView.addJavascriptInterface(new Object() {
            @JavascriptInterface
            public void setCookie(String cookies) {
                cookieStr = cookies;
            }

            @JavascriptInterface
            public void httpRequest(String method, String url, String body, String reqId) {
                Request.Builder builder = new Request.Builder().url(url);
                
                if (!cookieStr.isEmpty()) builder.addHeader("Cookie", cookieStr);
                builder.addHeader("Content-Type", "application/json");
                builder.addHeader("X-Requested-With", "mark.via.gp");
                builder.addHeader("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36");
                builder.addHeader("Origin", "https://me-tp.qureo.education");
                builder.addHeader("Referer", "https://me-tp.qureo.education/");

                RequestBody reqBody = null;
                if (body != null && !body.isEmpty() && !body.equals("null")) {
                    reqBody = RequestBody.create(body, MediaType.parse("application/json; charset=utf-8"));
                }

                builder.method(method, reqBody);
                Request request = builder.build();

                client.newCall(request).enqueue(new Callback() {
                    @Override
                    public void onFailure(Call call, IOException e) {
                        sendJsResponse(reqId, "{\"error\":\"" + e.getMessage() + "\"}");
                    }
                    @Override
                    public void onResponse(Call call, Response response) throws IOException {
                        String respBody = response.body() != null ? response.body().string() : "{}";
                        // إرسال الكوكيز الجديدة لو موجودة
                        String newCookies = response.header("Set-Cookie");
                        
                        String escapedBody = respBody.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "").replace("\r", "");
                        String js = "window.onBridgeResponse('" + reqId + "', '" + escapedBody + "', " + response.code() + ")";
                        runOnUiThread(() -> webView.evaluateJavascript(js, null));
                    }
                });
            }

            @JavascriptInterface
            public void notify(String title, String msg) {
                NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
                String channelId = "qureo_notif";
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    nm.createNotificationChannel(new android.app.NotificationChannel(channelId, "Qureo", NotificationManager.IMPORTANCE_HIGH));
                }
                NotificationCompat.Builder builder = new NotificationCompat.Builder(MainActivity.this, channelId)
                        .setSmallIcon(android.R.drawable.ic_dialog_info)
                        .setContentTitle(title).setContentText(msg).setPriority(NotificationCompat.PRIORITY_HIGH);
                nm.notify((int) System.currentTimeMillis(), builder.build());
            }
        }, "AndroidNative");

        webView.loadUrl("file:///android_asset/index.html");
    }

    private void sendJsResponse(String reqId, String json) {
        String js = "window.onBridgeResponse('" + reqId + "', '" + json.replace("'", "\\'") + "', 200)";
        runOnUiThread(() -> webView.evaluateJavascript(js, null));
    }

    @Override
    public void onBackPressed() {
        if (webView.canGoBack()) webView.goBack();
        else super.onBackPressed();
    }
}
