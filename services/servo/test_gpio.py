from services.servo.gpio import GPIO

def main():
    gpio = GPIO()
    ok = gpio.open('/dev/gpiochip3', 20, consumer='blink')
    if not ok:
        print('open failed')
        return
    print('a')
    gpio.blink(count=10, interval=2)
    print('b')
    gpio.close()

if __name__ == '__main__':
    main()
