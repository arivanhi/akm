#include "AS726X.h"
#define ledMerah 2
#define ledIr 4
#define ledGlu 16
#define photoDioda 17

AS726X sensor;

void TCA9548A(uint8_t bus) {
  Wire.beginTransmission(0x70);  // TCA9548A address is 0x70
  Wire.write(1 << bus);          // send byte to select bus
  Wire.endTransmission();
  // Serial.print(bus);
}
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

void setup() {
  // put your setup code here, to run once:
  Wire.begin();
  Serial.begin(115200);
  pinMode(ledMerah, OUTPUT);
  pinMode(ledGlu, OUTPUT);
  pinMode(ledIr, OUTPUT);

  TCA9548A(2);
  if (!sensor.begin()) {
    Serial.println("sensor failed to connect");
    for (;;)
      ;
  }
  Serial.println("sensor 1 connect");
  TCA9548A(3);
  if (!sensor.begin()) {
    Serial.println("sensor failed to connect");
    for (;;)
      ;
  }
  Serial.println("sensor 2 connect");
  delay(1000);
}

String asamUrat() {
  digitalWrite(ledMerah, HIGH);
  TCA9548A(2);
  String data;

  float violet[500];
  float blue[500];
  float green[500];
  float yellow[500];
  float orange[500];
  float red[500];

  for (int i = 0; i < 20; i++) {
    sensor.takeMeasurements();
    violet[i] = sensor.getCalibratedViolet();
    blue[i] = sensor.getCalibratedBlue();
    green[i] = sensor.getCalibratedGreen();
    yellow[i] = sensor.getCalibratedYellow();
    orange[i] = sensor.getCalibratedOrange();
    red[i] = sensor.getCalibratedRed();
    delay(500);
  }


  data = arrayToString(violet, 20);
  data += "," + arrayToString(blue, 20);
  data += "," + arrayToString(green, 20);
  data += "," + arrayToString(yellow, 20);
  data += "," + arrayToString(orange, 20);
  data += "," + arrayToString(red, 20);

  return data;
}

void loop() {
  // put your main code here, to run repeatedly:
  float violet;
  float blue;
  float green;
  float yellow;
  float orange;
  float red;
  String data;

  Serial.print("asam_urat: ");
  digitalWrite(ledMerah, HIGH);
  TCA9548A(2);
  sensor.takeMeasurements();
  violet = sensor.getCalibratedViolet();
  blue = sensor.getCalibratedBlue();
  green = sensor.getCalibratedGreen();
  yellow = sensor.getCalibratedYellow();
  orange = sensor.getCalibratedOrange();
  red = sensor.getCalibratedRed();

  data = String(violet);
  data += "," + String(blue);
  data += "," + String(green);
  data += "," + String(yellow);
  data += "," + String(orange);
  data += "," + String(red);

  Serial.println(data);
  delay(1000);

  Serial.print("kolesterol: ");
  digitalWrite(ledIr, HIGH);
  TCA9548A(3);
  sensor.takeMeasurements();
  violet = sensor.getCalibratedViolet();
  blue = sensor.getCalibratedBlue();
  green = sensor.getCalibratedGreen();
  yellow = sensor.getCalibratedYellow();
  orange = sensor.getCalibratedOrange();
  red = sensor.getCalibratedRed();

  data = String(violet);
  data += "," + String(blue);
  data += "," + String(green);
  data += "," + String(yellow);
  data += "," + String(orange);
  data += "," + String(red);

  Serial.println(data);
  delay(1000);
}
