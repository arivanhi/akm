#include <AS726X.h>
#include <Wire.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <NTPClient.h>
#include <WiFiUdp.h>
#include <EEPROM.h>

AS726X sensor;

//http://cemti.org/api_auk/update/1

const char* ssid = "esp1";
const char* password = "11111111";
const char* serverUrl1 = "http://cemti.org/api_asamurat/update/1";
const char* serverUrl2 = "https://data_akm.qbyte.web.id/asam_urat/api.php";  


// NTP Client Configuration
WiFiUDP ntpUDP;
NTPClient timeClient(ntpUDP, "pool.ntp.org", 7 * 3600, 60000); // 7 jam untuk WIB
int id = 1;
#define ledM 4
#define tb 16
#define ledTB 17
#define resetBtn 19 // Tombol untuk reset EEPROM, pin sesuai dengan koneksi
#define target_data 20

int id_pasien = 0;  // Variabel ID pasien, akan disimpan di EEPROM


float violet[500];
float blue[500];
float green[500];
float yellow[500];
float orange[500];
float red[500];

String arrayToString(float arr[], int size) {
  String result = "";
  for (int i = 0; i < size; i++) {
    result += String(arr[i], 2);
    if (i < size - 1) {
      result += ",";
    }
  }
  return result;
}

String getCurrentTime() {
  timeClient.update();
  return timeClient.getFormattedTime();
}

void setup() {
  
  pinMode(ledM, OUTPUT);
  pinMode(ledTB, OUTPUT);
  pinMode(tb, INPUT_PULLUP);
  pinMode(resetBtn, INPUT_PULLUP);  // Tombol reset untuk EEPROM
  Wire.begin();

  Serial.begin(115200);
Serial.println("Target Data " +  
String(target_data));
  // Membaca ID Pasien dari EEPROM (misalnya pada alamat 0)
  EEPROM.begin(512); // Alokasi memori EEPROM
  id_pasien = EEPROM.read(0);  // Baca ID pasien dari alamat 0
  if (id_pasien == 255) {  // Cek jika belum ada data (nilai default EEPROM adalah 255)
    id_pasien = 1;  // Atur ID pasien awal jika belum ada
    EEPROM.write(0, id_pasien);  // Simpan ke EEPROM
    EEPROM.commit();  // Pastikan perubahan disimpan
  }
Serial.println("id pasien terakhir " + String(id_pasien-1));
Serial.println("Asam Urat");
Serial.println(ssid);
Serial.println(password);
Serial.println(resetBtn);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
 digitalWrite(ledM, 1);
  }
    digitalWrite(ledM, 1);
  Serial.println("WiFi connected.");

  // Start NTP Client
  timeClient.begin();

  if (!sensor.begin()) {
    Serial.println("Sensor AS726x tidak terdeteksi! Periksa koneksi.");
    while (1);
  }
  //sensor.setMeasurementMode(3);
}

void resetEEPROM() {
  Serial.println("Resetting EEPROM...");
  EEPROM.write(0, 255);  // Set nilai ID pasien menjadi 255 (default)
  EEPROM.commit();  // Simpan perubahan ke EEPROM
  id_pasien = 1;  // Atur ID pasien ke 1 setelah reset
  Serial.println("EEPROM reset complete.");
}

void loop() {
  if (digitalRead(tb) == 0) {
      digitalWrite(ledM, 1);
    Serial.println("id_pasian terakir " + String(id_pasien-1));
    digitalWrite(ledTB,1);
    //sensor.setIntegrationTime(255);  // Set waktu integrasi lebih pendek
    //sensor.setMeasurementMode(3);   // Mode continuous

    for (int i = 0; i < target_data; i++) {
      //while (!sensor.dataReady()) { }  // Tunggu data siap
   //   sensor.readRawValues();  // Ambil data terbaru
      sensor.takeMeasurements();
      violet[i] = sensor.getCalibratedViolet();
      blue[i] = sensor.getCalibratedBlue();
      green[i] = sensor.getCalibratedGreen();
      yellow[i] = sensor.getCalibratedYellow();
      orange[i] = sensor.getCalibratedOrange();
      red[i] = sensor.getCalibratedRed();
    }
    /*for (int i = 0; i < target_data; i++) {  // Mengambil 500 data
      sensor.takeMeasurements();
      violet[i] = sensor.getCalibratedViolet();
    }

    for (int i = 0; i < target_data; i++) {  // Mengambil 500 data
      sensor.takeMeasurements();
      blue[i] = sensor.getCalibratedBlue();
    }
    for (int i = 0; i < target_data; i++) {  // Mengambil 500 data
      sensor.takeMeasurements();
      green[i] = sensor.getCalibratedGreen();
    }
    for (int i = 0; i < target_data; i++) {  // Mengambil 500 data
      sensor.takeMeasurements();
      yellow[i] = sensor.getCalibratedYellow();
    }
    for (int i = 0; i < target_data; i++) {  // Mengambil 500 data
      sensor.takeMeasurements();
      orange[i] = sensor.getCalibratedOrange();
    }
    for (int i = 0; i < target_data; i++) {  // Mengambil 500 data
      sensor.takeMeasurements();
      red[i] = sensor.getCalibratedRed();
    }*/
digitalWrite(ledTB,0);
Serial.println("Selesai ambil data");
digitalWrite(ledM, 0);
    // Debugging data
  
    // Create JSON payload with updated id_pasien
    String jsonPayload = "{";
    jsonPayload += "\"id_pasien\": " + String(id_pasien) + ", ";  // Menggunakan id_pasien
    jsonPayload += "\"ins_time\": \"" + getCurrentTime() + "\", ";
    jsonPayload += "\"violet\":[" + arrayToString(violet, target_data) + "],";
    jsonPayload += "\"blue\":[" + arrayToString(blue, target_data) + "],";
    jsonPayload += "\"green\":[" + arrayToString(green, target_data) + "],";
    jsonPayload += "\"yellow\":[" + arrayToString(yellow, target_data) + "],";
    jsonPayload += "\"orange\":[" + arrayToString(orange, target_data) + "],";
    jsonPayload += "\"red\":[" + arrayToString(red, target_data) + "]";
    jsonPayload += "}";

    // Serial.println("JSON Payload:");
    // Serial.println(jsonPayload);

    if (WiFi.status() == WL_CONNECTED) {
      // Mengirimkan data ke API pertama
      HTTPClient http1;
      http1.begin(serverUrl1);
      http1.addHeader("Content-Type", "application/json");
      int httpResponseCode1 = http1.POST(jsonPayload);

      if (httpResponseCode1 > 0) {
        String response1 = http1.getString();
        Serial.println("Response from API 1: " + response1);
      } else {
        Serial.printf("Error sending data to API 1. HTTP code: %d\n", httpResponseCode1);
      }
      http1.end();

      // Mengirimkan data ke API kedua
      HTTPClient http2;
      http2.begin(serverUrl2);
      http2.addHeader("Content-Type", "application/json");
      int httpResponseCode2 = http2.POST(jsonPayload);

      if (httpResponseCode2 > 0) {
        String response2 = http2.getString();
        Serial.println("Response from API 2: " + response2);
      } else {
        Serial.printf("Error sending data to API 2. HTTP code: %d\n", httpResponseCode2);
      }
      http2.end();
    } else {
      Serial.println("WiFi not connected.");
    }
  Serial.println("Selesai id pasien terbaru " + String(id_pasien));
    // Increment id_pasien after sending data
    id_pasien++;  // Tambah id_pasien untuk data berikutnya
    EEPROM.write(0, id_pasien);  // Simpan ID pasien terbaru ke EEPROM
    EEPROM.commit();  // Pastikan perubahan disimpan

  
  } else {
      digitalWrite(ledM, 0);
    digitalWrite(ledTB, 0);
    delay(200);
    digitalWrite(ledTB, 1);
    delay(200);
  }

  // Tombol reset untuk menghapus data EEPROM
  if (digitalRead(resetBtn) == LOW) {
    resetEEPROM();
  }
}

// Fungsi untuk mereset EEPROM
