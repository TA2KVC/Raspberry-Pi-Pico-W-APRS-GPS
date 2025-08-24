import machine
import time
import network
import usocket as socket
from machine import Pin, UART, ADC
from micropyGPS import MicropyGPS
import utime
import ntptime

print("TA2KVC Raspberry Pi Pico W - GY-NEO6MV2 GPS - APRS Sistemi")

# ========= AYARLAR =========
WIFI_SSID = 'xxxxxx'
WIFI_PASS = 'xxxxxxxxxxxxxxxxx'
CALLSIGN = 'XXXXX-X'
PASSCODE = 'xxxxxxxxxx'  #CALLSIGN passcode
MACHINE_NAME = 'RaspberryPi_Pico-W'
APRS_HOST = "148.251.228.231"
APRS_PORT = 14580
DEFAULT_LAT = 40.xxxxx
DEFAULT_LON = 32.xxxxx
# ===========================

led = Pin("LED", Pin.OUT)
uart = UART(0, baudrate=9600, tx=Pin(0), rx=Pin(1))
gps = MicropyGPS()
temp_sensor = ADC(4)
gps_locked = False  # GPS bağlantısı bayrağı
#led.off()

# --- Wi-Fi ---
def wifi_connect():
    sta = network.WLAN(network.STA_IF)
    if not sta.active():
        sta.active(True)
    if not sta.isconnected():
        print("Wi-Fi bağlanıyor...")
        sta.connect(WIFI_SSID, WIFI_PASS)
        for _ in range(100):
            if sta.isconnected():
                break
            time.sleep(0.1)
    if sta.isconnected():
        ip = sta.ifconfig()[0]
        print("✅ Wi-Fi Bağlandı!")
        print("SSID:", WIFI_SSID)
        print("IP  :", ip)
        return True
    else:
        print("❌ Wi-Fi bağlanamadı!")
        return False

# --- Dahili sıcaklık ---
def sicaklik():
    adc_value = temp_sensor.read_u16()
    voltage = adc_value * (3.3 / 65535.0)
    scklk = 27 - (voltage - 0.706) / 0.001721
    return round(scklk)

# --- LED ---
def blink(times=15, t_on=0.1, t_off=0.1):
    for _ in range(times):
        led.on(); time.sleep(t_on)
        led.off(); time.sleep(t_off)

# --- APRS sembol ---
def aprs_symbol(last_lat, last_lon, lat, lon):
    delta = abs(lat - last_lat) + abs(lon - last_lon)
    if delta > 0.5:
        return '>'  # sabit
    elif delta > 0.01 and delta < 0.5:
        return '['  # yürüyüş
    else:
        return 'x'  # hızlı

# --- Gönderim periyodu ---
def get_send_period(last_lat, last_lon, lat, lon):
    delta = abs(lat - last_lat) + abs(lon - last_lon)
    if delta < 0.0002:
        return 90
    elif delta < 0.001:
        return 60
    else:
        return 30

# --- APRS lat/lon format ---
def format_aprs(lat, lat_dir, lon, lon_dir):
    lat_dd = int(lat)
    lat_mm = (lat - lat_dd) * 60
    lon_dd = int(lon)
    lon_mm = (lon - lon_dd) * 60
    lat_str = "{:02d}{:05.2f}{}".format(lat_dd, lat_mm, lat_dir)
    lon_str = "{:03d}{:05.2f}{}".format(lon_dd, lon_mm, lon_dir)
    return lat_str, lon_str

# --- Tarih ve saat alma (saniye yok) ---
def get_date_time_from_gps_or_ntp(gps_timestamp=None):
    try:
        if gps_timestamp is not None:
            hour, minute, _, day, month, year = gps_timestamp
        else:
            ntptime.settime()
            tm = utime.localtime()
            print(tm)
            year, month, day, hour, minute = tm[0], tm[1], tm[2], tm[3], tm[4]
        tarih = "{:02}-{:02}-{:02}".format(day, month, year)
        saat = "{:02}:{:02}".format(hour, minute)
        return tarih, saat
    except:
        tm = utime.localtime()
        tarih = "{:02}-{:02}-{:04}".format(tm[2], tm[1], tm[0])
        saat = "{:02}:{:02}".format(tm[3], tm[4])
        return tarih, saat

# --- APRS gönderimi ---
def aprs_send(lat_str, lon_str, alt, sat, temp, symbol, tarih, saat):
    try:
        pkt = f"!{lat_str}/{lon_str}{symbol} TA2KVC Raspberry Pi Pico APRS Tarih:{tarih} Saat:{saat} Yükselti:{alt}m GPS Uydu:{sat} Sıcaklık:{temp}°C"
        sck = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sck.connect((APRS_HOST, APRS_PORT))
        sck.send(('user %s pass %s vers %s \n' % (CALLSIGN, PASSCODE, MACHINE_NAME)).encode('utf-8'))
        sck.send(('%s>APE100:%s\n' % (CALLSIGN, pkt)).encode('utf-8'))
        print("APRS Gönderildi:", pkt)
        blink(15,0.05,0.05)
        sck.close()
    except Exception as e:
        print("APRS hata:", e)

# --- GPS uydu bekleme  ---
def wait_gps_lock(timeout_min=3):
    start_time = time.time()
    #gps_reported = False
    while (time.time() - start_time) < timeout_min * 60:
        if uart.any():
            for b in uart.read():
                gps.update(chr(b))
        if gps.satellites_in_use > 0 and gps.latitude[0] is not None:
            lat = gps.latitude[0] + gps.latitude[1]/60
            lon = gps.longitude[0] + gps.longitude[1]/60
            lat_dir = gps.latitude[2]
            lon_dir = gps.longitude[2]
            alt = gps.altitude
            sat = gps.satellites_in_use
            hour, minute, second = gps.timestamp[0], gps.timestamp[1], gps.timestamp[2]
            day, month, year = gps.date[0], gps.date[1], gps.date[2]
            hour = (hour + 3) % 24  # Türkiye saati
            return lat, lat_dir, lon, lon_dir, sat, alt, (hour, minute, second, day, month, year)
        else:
            print("GPS uydu bekleniyor...")
            time.sleep(1)
    print("Uyduya bağlanılamadı, default konum kullanılıyor")
    lt = DEFAULT_LAT; ln = DEFAULT_LON
    return lt, 'N', ln, 'E', 0, 0, None

# --- Ana Döngü ---
wifi_connect()
print("Sistem Hazır")
blink(2,0.2,0.2)

last_lat = DEFAULT_LAT
last_lon = DEFAULT_LON
last_send = 0
send_period = 80

while True:
    try:
        lat, lat_dir, lon, lon_dir, sat, alt, gps_timestamp = wait_gps_lock(3)
        temp = sicaklik()
        symbol = aprs_symbol(last_lat, last_lon, lat, lon)
        lat_aprs, lon_aprs = format_aprs(lat, lat_dir, lon, lon_dir)
        send_period = get_send_period(last_lat, last_lon, lat, lon)

        tarih, saat = get_date_time_from_gps_or_ntp(gps_timestamp)
        if sat > 0 and not gps_locked:
            print(f"GPS uydusuna bağlandı! Uydu sayısı: {sat}")
            gps_locked = True
        if time.time() - last_send > send_period:
            aprs_send(lat_aprs, lon_aprs, alt, sat, temp, symbol, tarih, saat)
            last_send = time.time()
            last_lat = lat
            last_lon = lon

        time.sleep(5)

    except Exception as e:
        print("Ana döngü hatası:", e)
        time.sleep(5)

