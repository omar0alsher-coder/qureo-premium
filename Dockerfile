FROM python:3.11-alpine

# تثبيت الأدوات
RUN apk add --no-cache curl unzip libc6-compat

# تحميل Xray
RUN curl -L -o xray.zip https://github.com/XTLS/Xray-core/releases/download/v1.8.24/Xray-linux-64.zip && \
    unzip xray.zip && \
    mv xray /usr/local/bin/xray && \
    chmod +x /usr/local/bin/xray && \
    rm xray.zip

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# سكربت التشغيل
RUN echo '#!/bin/sh' > start.sh && \
    echo '/usr/local/bin/xray -c config.json &' >> start.sh && \
    echo 'sleep 2' >> start.sh && \
    echo 'python app.py' >> start.sh && \
    chmod +x start.sh

CMD ["./start.sh"]
