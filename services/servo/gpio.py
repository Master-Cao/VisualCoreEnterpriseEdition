import time
from typing import Optional


class GPIO:
    def __init__(self):
        self._chip = None
        self._line = None
        self._line_offset: Optional[int] = None
        self.healthy: bool = False

    def open(self, chip: str, pin: int, consumer: str = "gpio-demo") -> bool:
        try:
            import gpiod
            self.close()
            self._line_offset = int(pin)
            self._chip = gpiod.Chip(chip)
            self._line = self._chip.get_line(self._line_offset)
            self._line.request(consumer=consumer, type=gpiod.LINE_REQ_DIR_OUT, default_vals=[0])

            self.healthy = True
            return True
        except Exception:
            self.healthy = False
            return False

    def set(self, value: int) -> bool:
        try:
            if self._line is not None:
                self._line.set_value(1 if value else 0)
                return True
            return False
        except Exception:
            self.healthy = False
            return False

    def high(self) -> bool:
        return self.set(1)

    def low(self) -> bool:
        return self.set(0)

    def get(self) -> Optional[int]:
        try:
            if self._line is not None:
                v = self._line.get_value()
                return int(v)
            return None
        except Exception:
            return None

    def blink(self, count: int = 10, interval: float = 2.0) -> bool:
        if not self.healthy:
            return False
        try:
            for _ in range(max(1, int(count))):
                self.high()
                time.sleep(interval)
                self.low()
                time.sleep(interval)
            return True
        except Exception:
            self.healthy = False
            return False

    def close(self):
        try:
            if self._line is not None:
                try:
                    self._line.set_value(0)
                except Exception:
                    pass
                try:
                    self._line.release()
                except Exception:
                    pass
                self._line = None
            if self._chip is not None:
                try:
                    self._chip.close()
                except Exception:
                    pass
                self._chip = None
        finally:
            self.healthy = False
