#include <Wire.h>
#include <Adafruit_ICM20948.h>
#include <Adafruit_Sensor.h>

Adafruit_ICM20948 sensor1;
Adafruit_ICM20948 sensor2;

#define SENSOR1_ADDRESS 0x68
#define SENSOR2_ADDRESS 0x69

// 50 Hz sampling
// 50,000 µs = 50 ms = 20 Hz
// 10,000 µs = 10 ms = 100 Hz
// 1,000 µs = 1 ms = 1000 Hz
const unsigned long SAMPLE_PERIOD_US = 1000;

unsigned long nextSample = 0;

void setup()
{
  Serial.begin(2000000);

  while (!Serial) {
    delay(10);
  }

  // Start I2C
  Wire.begin();

  // Use standard I2C speed for maximum reliability
  Wire.setClock(800000);
  // Wire.setClock(400000);

  delay(100);

  Serial.println("# Dual ICM-20948 logger");
  Serial.println("# Initializing...");

  // -------------------------------
  // Sensor 1
  // -------------------------------

  if (!sensor1.begin_I2C(SENSOR1_ADDRESS, &Wire))
  {
    Serial.println("# ERROR: Sensor 1 not found at 0x68");

    while (1) {
      delay(1000);
    }
  }

  Serial.println("# Sensor 1 OK");


  // -------------------------------
  // Sensor 2
  // -------------------------------

  if (!sensor2.begin_I2C(SENSOR2_ADDRESS, &Wire))
  {
    Serial.println("# ERROR: Sensor 2 not found at 0x69");

    while (1) {
      delay(1000);
    }
  }

  Serial.println("# Sensor 2 OK");


  // -------------------------------
  // Configure accelerometers
  // -------------------------------

  sensor1.setAccelRange(ICM20948_ACCEL_RANGE_4_G);
  sensor2.setAccelRange(ICM20948_ACCEL_RANGE_4_G);

  sensor1.setAccelRateDivisor(0);
  sensor2.setAccelRateDivisor(0);


  // -------------------------------
  // CSV header
  // -------------------------------

  Serial.println(
    "time_us,"
    "ax1,ay1,az1,"
    "ax2,ay2,az2"
  );

  nextSample = micros();
}


void loop()
{
  unsigned long now = micros();

  if ((long)(now - nextSample) >= 0)
  {
    nextSample += SAMPLE_PERIOD_US;

    // ----------------------------------
    // Sensor 1
    // ----------------------------------

    sensors_event_t accel1;
    sensors_event_t gyro1;
    sensors_event_t temp1;
    sensors_event_t mag1;

    sensor1.getEvent(
      &accel1,
      &gyro1,
      &temp1,
      &mag1
    );


    // ----------------------------------
    // Sensor 2
    // ----------------------------------

    sensors_event_t accel2;
    sensors_event_t gyro2;
    sensors_event_t temp2;
    sensors_event_t mag2;

    sensor2.getEvent(
      &accel2,
      &gyro2,
      &temp2,
      &mag2
    );


    // ----------------------------------
    // Output CSV
    // ----------------------------------

    Serial.print(now);
    Serial.print(",");

    Serial.print(accel1.acceleration.x, 4);
    Serial.print(",");
    Serial.print(accel1.acceleration.y, 4);
    Serial.print(",");
    Serial.print(accel1.acceleration.z, 4);
    Serial.print(",");

    Serial.print(accel2.acceleration.x, 4);
    Serial.print(",");
    Serial.print(accel2.acceleration.y, 4);
    Serial.print(",");
    Serial.println(accel2.acceleration.z, 4);
  }
}