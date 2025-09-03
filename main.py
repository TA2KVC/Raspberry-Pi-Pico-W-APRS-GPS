import machine, network, socket, utime, dht, os
from volkan5110 import PCD8544_FB
from machine import Pin, UART, ADC, SPI, SoftI2C
from micropyGPS import MicropyGPS
import ntptime

print("TA2KVC Raspberry Pi Pico W - GY-NEO7M GPS - APRS Sistemi")

# ========= AYARLAR =========
WIFI_SSID = 'Droid'
WIFI_PASS = 'VOLKAN'
CALLSIGN = 'XX0XXX'
PASSCODE = 'xxxxx'
MACHINE_NAME = 'RaspberryPi_Pico-W'
APRS_SERVER = "euro.aprs2.net"
APRS_PORT = 14580
DEFAULT_LAT = 40.xxxxx
DEFAULT_LON = 32.xxxxx
LAST_GPS_FILE = "last_gps.txt"
APRS_COUNT_FILE = "aprs_count.txt"

# Sensör Ayarları
led = Pin("LED", Pin.OUT)
uart = UART(0, baudrate=9600, tx=Pin(0), rx=Pin(1))
gps = MicropyGPS()
temp_sensor = ADC(4)
dht_sensor = dht.DHT11(machine.Pin(15))
gps_locked = False

# --- Nokia 5110 LCD ---
spi = SPI(1)
spi.init(baudrate=2000000, polarity=0, phase=0)
dc = Pin(14)
cs = Pin(13)
rst = Pin(12)
lcd = PCD8544_FB(spi, cs, dc, rst)

def nokia():
    lcd.fill(0)
    lcd.draw_text(10, 0, "* TA2KVC *", color=1)
    lcd.draw_text(0,16,"Raspberry Pi")
    lcd.draw_text(0,24,"Pico W APRS")
    lcd.draw_text(0,40,"TA2KVC VOLKAN")
    lcd.show()
    utime.sleep(2)
    lcd.clear()
    
# --- Wi-Fi ---
def wifi_connect():
    nokia()
    sta = network.WLAN(network.STA_IF)
    if not sta.active():
        sta.active(True)
    if not sta.isconnected():
        print("Wi-Fi bağlanıyor...")
        sta.connect(WIFI_SSID, WIFI_PASS)
        lcd.fill(0)
        lcd.draw_text(10,0,"* TA2KVC *")
        lcd.draw_text(30,16,"WIFI")
        lcd.draw_text(5,32,"Baglaniyor...")
        lcd.show()
        utime.sleep(2)
        lcd.clear()
        for _ in range(100):
            if sta.isconnected():
                break
            utime.sleep(0.1)
    if sta.isconnected():
        ip = sta.ifconfig()[0]
        print("✅ Wi-Fi Bağlandı!")
        print("SSID:", WIFI_SSID)
        print("IP  :", ip)
        lcd.fill(0)
        lcd.draw_text(10,0,"* TA2KVC *")
        lcd.draw_text(0,8,"WIFI Baglandi!")
        lcd.draw_text(0,16,"SSID: "+WIFI_SSID)
        lcd.draw_text(0,24,"IP verildi: ")
        lcd.draw_text(0,32,ip)
        lcd.show()
        utime.sleep(2)
        lcd.clear()
        return True
    else:
        print("❌ Wi-Fi bağlanamadı!")
        lcd.fill(0)
        lcd.draw_text(10,0,"* TA2KVC *")
        lcd.draw_text(0,24,"Wi-Fi Yok!")
        lcd.show()
        lcd.clear()
        return False

# --- Dahili sıcaklık ---
def sicaklik():
    adc_value = temp_sensor.read_u16()
    voltage = adc_value * (3.3 / 65535.0)
    scklk = 27 - (voltage - 0.706) / 0.001721
    return round(scklk)

def read_dht11(retry=3, delay=2):
    DHTerror_printed = False
    for _ in range(retry):
        try:
            utime.sleep(1)  # DHT11 için minimum 1 saniye bekleme
            dht_sensor.measure()
            t = int(dht_sensor.temperature())   # sıcaklık tam sayı
            h = int(dht_sensor.humidity())     # nem tam sayı
            return t, h
        except Exception as e:
            if not DHTerror_printed:
                print("DHT11 okuma hatası:", e)
                lcd.fill(0)
                lcd.draw_text(10,0,"* TA2KVC *")
                lcd.draw_text(0,16,"DHT-11")
                lcd.draw_text(0,24,"Sensor")
                lcd.draw_text(0,32,"HATASI!")
                lcd.show()
                DHTerror_printed = True
            utime.sleep(2)
            #lcd.clear()
    print("DHT11 okunamadı, -1 değeri verildi.")
    return -1, -1

# --- Son GPS Konum ve APRS sayacı ---
def read_last_gps():
    try:
        with open(LAST_GPS_FILE) as f:
            data = f.read().split(',')
            return float(data[0]), float(data[1]), float(data[2])
    except:
        return DEFAULT_LAT, DEFAULT_LON, 0


def save_last_gps(lat, lon, alt):
    with open(LAST_GPS_FILE,'w') as f:
        f.write(f"{lat},{lon},{alt}")


def save_last_gps(lat, lon, alt):
    # GPS verisi geçerli mi kontrol et
    if (lat is None or lon is None or alt is None or
        lat == 0.0 or lon == 0.0 or alt == 0.0):
        print("Geçersiz GPS verisi, kayıt yapılmadı.")
        lcd.fill(0)
        lcd.draw_text(10,0,"* TA2KVC *")
        lcd.draw_text(0,16,"Gecersiz")
        lcd.draw_text(0,24,"GPS Verisi")
        lcd.draw_text(0,32,"Kayıt")
        lcd.draw_text(0,40,"Yapilmadi!")
        lcd.show()
        utime.sleep(2)
        lcd.clear()
        return
    try:
        with open(LAST_GPS_FILE, 'w') as f:
            f.write(f"{lat},{lon},{alt}")
        #print("Son GPS konumu kaydedildi.")
    except Exception as e:
        print("GPS konumu kaydedilemedi:", e)
        lcd.fill(0)
        lcd.draw_text(10,0,"* TA2KVC *")
        lcd.draw_text(0,16,"GPS Verisi")
        lcd.draw_text(0,24,"Kaydedilemedi:")
        lcd.show()
        utime.sleep(2)
        lcd.clear()

def read_aprs_count():
    try:
        with open(APRS_COUNT_FILE) as f: return int(f.read())
    except: return 0

def save_aprs_count(count):
    with open(APRS_COUNT_FILE,'w') as f: f.write(str(count))

# --- LED ---
def blink(times=15, t_on=0.1, t_off=0.1):
    for _ in range(times):
        led.on(); utime.sleep(t_on)
        led.off(); utime.sleep(t_off)

# --- APRS sembol ---
def aprs_symbol(last_lat, last_lon, lat, lon):
    delta = abs(lat - last_lat) + abs(lon - last_lon)
    if delta > 0.005:
        return '>'  # fast
    elif delta > 0.0005:
        return '['  # yürüyüş
    else:
        return 'x'  # sabit

# --- Gönderim periyodu ---
def get_send_period(last_lat, last_lon, lat, lon):
    delta = abs(lat - last_lat) + abs(lon - last_lon)
    if delta > 0.005:
        return 15
    elif delta > 0.0009:
        return 30
    else:
        return 90

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
        tarih = "{:02}.{:02}.{:02}".format(day, month, year)
        saat = "{:02}.{:02}".format(hour, minute)
        return tarih, saat
    except:
        tm = utime.localtime()
        tarih = "{:02}-{:02}-{:04}".format(tm[2], tm[1], tm[0])
        saat = "{:02}:{:02}".format(tm[3], tm[4])
        return tarih, saat

# --- APRS gönderimi ---
def aprs_send(lat_str, lon_str, alt, sat, temp, hum, symbol, tarih, saat):
    try:
        pkt = f"!{lat_str}/{lon_str}{symbol} TA2KVC Raspberry Pi Pico APRS Tarih:{tarih} Saat:{saat} Yükselti:{alt}m GPS Uydu:{sat} Sıcaklık:{temp}°C Nem: %{hum}"
        addr = socket.getaddrinfo(APRS_SERVER, APRS_PORT)[0][-1]
        sck = socket.socket()
        sck.connect(addr)
        login_str = "user {} pass {} vers RaspberryPi_Pico-W 1.0\n".format(CALLSIGN, PASSCODE)
        sck.send(login_str.encode())
        packet = "{}>APRPI0,TCPIP*:{}\n".format(CALLSIGN, pkt)
        sck.send(packet.encode())
        print("Paket gönderildi:", packet)
        blink(15,0.05,0.05)
        sck.close()
    except Exception as e:
        print("APRS hata:", e)
        lcd.fill(0)
        lcd.draw_text(10,0,"* TA2KVC *")
        lcd.draw_text(0,24,"APRS")
        lcd.draw_text(0,32,"HATASI")
        lcd.show()
        utime.sleep(1)
        lcd.clear()

# --- GPS uydu bekleme (tek seferlik mesaj) ---
def wait_gps_lock(timeout_min=3):
    start_time = utime.time()
    waiting_printed = False
    dots = 0
    #gps_reported = False
    while (utime.time() - start_time) < timeout_min * 60:
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
            if not waiting_printed:
            #if dots == 0:
                print("⏳ GPS uydu bekleniyor...")
                waiting_printed = True

            lcd.fill(0)
            lcd.draw_text(10,0,"* TA2KVC *")
            lcd.draw_text(30,16,"GPS")
            lcd.draw_text(20,24,"Uydusu")
            if dots == 0:
                lcd.draw_text(6, 32, "Bekleniyor   ")
            elif dots == 1:
                lcd.draw_text(6, 32, "Bekleniyor.  ")
            elif dots == 2:
                lcd.draw_text(6, 32, "Bekleniyor.. ")
            else:
                lcd.draw_text(6, 32, "Bekleniyor...")

            lcd.show()
            utime.sleep(0.5)
            dots = (dots + 1) % 4
            #waiting_printed = True
            #utime.sleep(3)
            #lcd.clear()
    print("Uyduya bağlanılamadı, default konum kullanılıyor")
    lt, ln, alt = read_last_gps()
    return lt, 'N', ln, 'E', 0, alt, None

# --- Ana Döngü ---
wifi_connect()
print("Sistem Hazır")
lcd.draw_text(0,40,"Sistem HAZIR!")
lcd.show()
utime.sleep(1)
blink(5,0.05,0.05)
last_lat, last_lon, last_alt = read_last_gps()
aprs_count = read_aprs_count()
last_send = 0
lcd.fill(0)

while True:
    try:
        lat, lat_dir, lon, lon_dir, sat, alt, gps_timestamp = wait_gps_lock(3)
        symbol = aprs_symbol(last_lat, last_lon, lat, lon)
        lat_aprs, lon_aprs = format_aprs(lat, lat_dir, lon, lon_dir)
        send_period = get_send_period(last_lat, last_lon, lat, lon)
        save_last_gps(lat, lon, alt)
        try:
            temp, hum = read_dht11()
        except Exception:
            temp, hum = sicaklik(), None  # Dahili sensör yedek

        tarih, saat = get_date_time_from_gps_or_ntp(gps_timestamp)
        
        # --- LCD Güncelle ---
        lcd.fill(0)
        lcd.draw_text(0,0,f"Lat: {(lat_aprs)}")
        lcd.draw_text(0,8,f"Lon: {(lon_aprs)}")
        lcd.draw_text(0,16,f"GPS Fix:{(sat)} Uydu")
        lcd.draw_text(0,24,f"T: {temp}°C N: %{hum}")
        lcd.draw_text(0,32,f"Pac:{(aprs_count)}  F:{(send_period)}")
        lcd.draw_text(0,40,f"Saat:{saat}")
        lcd.draw_text_mini(65,42,f"{tarih}")
        lcd.show()
        
        if sat > 0 and not gps_locked:
            print(f"GPS uydusuna bağlandı! Uydu sayısı: {sat}")
            gps_locked = True
        if utime.time() - last_send > send_period:
            aprs_send(lat_aprs, lon_aprs, alt, sat, temp, hum, symbol, tarih, saat)
            aprs_count += 1
            save_aprs_count(aprs_count)
            last_send = utime.time()
            last_lat = lat
            last_lon = lon

        utime.sleep(3)
        lcd.fill(0)
        
    except Exception as e:
        print("Ana döngü hatası:", e)
        lcd.fill(0)
        lcd.draw_text(10,0,"* TA2KVC *")
        lcd.draw_text(10,16,"ANA DONGU")
        lcd.draw_text(20,24,"HATASI:")
        lcd.draw_text(0,32, str(e))
        lcd.show()
        utime.sleep(2)
        lcd.clear()
        utime.sleep(1)


