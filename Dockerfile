# 1. Base Image: เริ่มต้นจากคอมพิวเตอร์ Linux ที่มี Python ติดตั้งไว้แล้ว
FROM python:3.11-slim

# 2. Set working directory
WORKDIR /app

# 3. Install ODBC Driver: ส่วนที่สำคัญที่สุด
# เราจะสวมบทเป็น root เพื่อติดตั้ง Driver ที่จำเป็น
USER root
RUN apt-get update && \
    apt-get install -y curl gnupg && \
    curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - && \
    curl https://packages.microsoft.com/config/debian/11/prod.list > /etc/apt/sources.list.d/mssql-release.list && \
    apt-get update && \
    ACCEPT_EULA=Y apt-get install -y msodbcsql17

# 4. Install Python libraries
# คัดลอกแค่ไฟล์ requirements.txt เข้าไปก่อนเพื่อความเร็วในการ build
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy the rest of the application code
# คัดลอกไฟล์โค้ดทั้งหมดของเราเข้าไปใน Server จิ๋ว
COPY . .

# 6. Command to run the application
# คำสั่งที่จะรันเมื่อเปิด Server นี้ขึ้นมา
CMD ["gunicorn", "connect_db:app", "--bind", "0.0.0.0:10000", "--workers", "4"]