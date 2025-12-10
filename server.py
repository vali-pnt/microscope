import io
import cv2
from threading import Condition
from picamera2 import Picamera2
from picamera2.encoders import JpegEncoder
from picamera2.outputs import FileOutput
import uvicorn
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import pigpio
from RpiMotorLib import RpiMotorLib

app = FastAPI()

LED_PIN = 21
X_PINS = [1, 12, 16, 20]
Y_PINS = [14, 15, 18, 23]
Z_PINS = [24, 25, 8, 7]
stepper_x = RpiMotorLib.BYJMotor("X", "28BYJ")
stepper_y = RpiMotorLib.BYJMotor("Y", "28BYJ")
stepper_z = RpiMotorLib.BYJMotor("Z", "28BYJ")

pi = pigpio.pi()
pi.set_PWM_frequency(LED_PIN, 1000)
pi.set_PWM_dutycycle(LED_PIN, 255)


class StreamingOutput(io.BufferedIOBase):
    def __init__(self):
        self.frame = None
        self.condition = Condition()

    def write(self, buf):
        with self.condition:
            self.frame = buf
            self.condition.notify_all()


output = StreamingOutput()
picam2 = Picamera2()
config = picam2.create_video_configuration(main={"size": (1280, 720)})
still_config = picam2.create_still_configuration(main={"size": (3280, 2464)})
picam2.configure(config)
picam2.start_recording(JpegEncoder(), FileOutput(output))


def generate_frames():
    while True:
        with output.condition:
            output.condition.wait()
            frame = output.frame

        header = (
            b"--FRAME\r\n"
            b"Content-Type: image/jpeg\r\n"
            b"Content-Length: " + str(len(frame)).encode() + b"\r\n\r\n"
        )
        yield header + frame + b"\r\n"


@app.get("/")
async def video_feed():
    return StreamingResponse(
        generate_frames(), media_type="multipart/x-mixed-replace; boundary=FRAME"
    )


@app.get("/still")
async def capture_still():
    picam2.stop_recording()
    picam2.configure(still_config)
    picam2.start()
    buf = picam2.capture_array()
    picam2.stop()
    picam2.configure(config)
    picam2.start_recording(JpegEncoder(), FileOutput(output))

    _, buffer = cv2.imencode(".jpg", buf)
    io_buf = io.BytesIO(buffer)
    return StreamingResponse(io_buf, media_type="image/x-exr")


@app.post("/step")
def step(x: int = 0, y: int = 0, z: int = 0):
    stepper_x.motor_run(X_PINS, steps=abs(x), ccwise=(x < 0))
    stepper_y.motor_run(Y_PINS, steps=abs(y), ccwise=(y < 0))
    stepper_z.motor_run(Z_PINS, steps=abs(z), ccwise=(z < 0))


@app.post("/set_light")
def set_light(brightness: int):
    pigpio.pi().set_PWM_dutycycle(LED_PIN, brightness)


uvicorn.run(app, host="0.0.0.0", port=8080)
