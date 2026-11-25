package com.qureo.solver;

import android.annotation.SuppressLint;
import android.app.NotificationManager;
import android.content.Intent;
import android.graphics.Color;
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
import java.net.CookieManager;
import java.net.CookiePolicy;
import java.util.List;

public class MainActivity extends AppCompatActivity {
    private WebView webView;
    private OkHttpClient client;
    private CookieManager cookieManager;

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        
        // إخفاء الخط الأسود (Full Screen + Notch Support)
        WindowCompat.setDecorFitsSystemWindows(getWindow(), false);
        WindowInsetsControllerCompat controller = new WindowInsetsControllerCompat(getWindow(), getWindow().getDecorView());
        controller.hide(WindowInsetsCompat.Type.systemBars());
        controller.setSystemBarsBehavior(WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);
        getWindow().setStatusBarColor(Color.TRANSPARENT);
        getWindow().setNavigationBarColor(Color.TRANSPARENT);

        startService(new Intent(this, KeepAliveService.class));

        // إدارة الكوكيز تلقائياً
        cookieManager = new CookieManager(null, CookiePolicy.ACCEPT_ALL);
        client = new OkHttpClient.Builder()
                .cookieJar(new JavaNetCookieJar(cookieManager))
                .followRedirects(false) // مهم جداً عشان نلقط الـ 302 والكوكيز في اللوجين
                .build();

        webView = new WebView(this);
        setContentView(webView);

        webView.getSettings().setJavaScriptEnabled(true);
        webView.getSettings().setDomStorageEnabled(true);
        webView.getSettings().setAllowFileAccess(true);
        webView.getSettings().setAllowContentAccess(true);
        webView.setWebViewClient(new WebViewClient());
        webView.setWebChromeClient(new WebChromeClient());

        webView.addJavascriptInterface(new Object() {
            @JavascriptInterface
            public void httpRequest(String method, String url, String body, String reqId) {
                Request.Builder builder = new Request.Builder().url(url);
                
                // هيدرز مختلفة حسب الدومين
                if (url.contains("me-portal.qureo.education")) {
                    builder.addHeader("Origin", "https://me-portal.qureo.education");
                    builder.addHeader("Referer", "https://me-portal.qureo.education/login");
                } else {
                    builder.addHeader("Origin", "https://me-tp.qureo.education");
                    builder.addHeader("Referer", "https://me-tp.qureo.education/course/javascript_en");
                    builder.addHeader("X-Requested-With", "mark.via.gp");
                }
                builder.addHeader("Content-Type", "application/json");
                builder.addHeader("User-Agent", "Mozilla/5.0 (Linux; Android 16; Infinix X6873) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/157.0.8103.50 Mobile Safari/537.36");

                RequestBody reqBody = null;
                if (body != null && !body.isEmpty() && !body.equals("null")) {
                    reqBody = RequestBody.create(body, MediaType.parse("application/json; charset=utf-8"));
                }

                builder.method(method, reqBody);
                Request request = builder.build();

                client.newCall(request).enqueue(new Callback() {
                    @Override
                    public void onFailure(Call call, IOException e) {
                        sendJsResponse(reqId, "{\"error\":\"" + e.getMessage() + "\"}", 500, "");
                    }
                    @Override
                    public void onResponse(Call call, Response response) throws IOException {
                        String respBody = response.body() != null ? response.body().string() : "{}";
                        
                        // تجميع الكوكيز الحالية لتمريرها للـ JS لو حابب يعرف رقم المادة
                        StringBuilder cookies = new StringBuilder();
                        List<HttpCookie> cookieList = cookieManager.getCookieStore().getCookies();
                        for (HttpCookie c : cookieList) {
                            cookies.append(c.getName()).append("=").append(c.getValue()).append("; ");
                        }

                        sendJsResponse(reqId, respBody, response.code(), cookies.toString());
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

    private void sendJsResponse(String reqId, String json, int statusCode, String cookies) {
        String escapedJson = json.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "").replace("\r", "");
        String escapedCookies = cookies.replace("'", "\\'");
        String js = "window.onBridgeResponse('" + reqId + "', '" + escapedJson + "', " + statusCode + ", '" + escapedCookies + "')";
        runOnUiThread(() -> webView.evaluateJavascript(js, null));
    }

    @Override
    public void onBackPressed() {
        if (webView.canGoBack()) webView.goBack();
        else super.onBackPressed();
    }
}
