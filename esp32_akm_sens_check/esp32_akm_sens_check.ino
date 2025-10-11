#include "AS726X.h"
#define ledMerah 2
#define ledIr 4
#define ledGlu 16
#define photoDioda 17

AS726X sensor;

void setup() {
  // put your setup code here, to run once:
  Wire.begin();
  Serial.begin(115200);
  pinMode(ledMerah, OUTPUT);
  pinMode(ledGlu, OUTPUT);
  pinMode(ledIr, OUTPUT);
  sensor.begin();
}

void loop() {
  // put your main code here, to run repeatedly:
  sensor.takeMeasurements();
  // Serial.println(sensor.getVersion()== SENSORTYPE_AS7263);
  Serial.print(" Reading: R[");
  Serial.print(sensor.getCalibratedR(), 2);
  Serial.print("] S[");
  Serial.print(sensor.getCalibratedS(), 2);
  Serial.print("] T[");
  Serial.print(sensor.getCalibratedT(), 2);
  Serial.print("] U[");
  Serial.print(sensor.getCalibratedU(), 2);
  Serial.print("] V[");
  Serial.print(sensor.getCalibratedV(), 2);
  Serial.print("] W[");
  Serial.print(sensor.getCalibratedW(), 2);
  Serial.println("]");

  digitalWrite(ledMerah, HIGH);
  digitalWrite(ledIr, HIGH);
  digitalWrite(ledGlu, HIGH);
  delay(1000);
}
