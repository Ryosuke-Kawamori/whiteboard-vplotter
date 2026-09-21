import unittest

from firmware import vplotter


class RecordingIO(vplotter.DummyIO):
    def __init__(self):
        super().__init__()
        self.servo_commands = []

    def servo(self, us):
        self.servo_commands.append(us)


class FakeLgpio:
    def __init__(self):
        self.calls = []

    def tx_servo(self, *args):
        self.calls.append(('servo', args))

    def tx_pwm(self, *args):
        self.calls.append(('pwm', args))


class VPlotterServoTest(unittest.TestCase):
    def setUp(self):
        self.io = RecordingIO()
        self.plotter = vplotter.Plotter(self.io)

    def test_initial_up_and_repeated_state_send_only_once(self):
        self.assertEqual([vplotter.SERVO_UP_US, 0], self.io.servo_commands)

        self.plotter.pen_up()

        self.assertEqual([vplotter.SERVO_UP_US, 0], self.io.servo_commands)

    def test_smooth_motion_in_both_directions(self):
        self.plotter.pen_down()
        down_commands = self.io.servo_commands[2:-1]
        self.assertEqual(vplotter.SERVO_DOWN_US, down_commands[-1])
        self.assertEqual(0, self.io.servo_commands[-1])
        down_direction = 1 if vplotter.SERVO_DOWN_US > vplotter.SERVO_UP_US else -1
        self.assertTrue(all(
            (b - a) * down_direction > 0
            for a, b in zip(down_commands, down_commands[1:])
        ))

        command_count = len(self.io.servo_commands)
        self.plotter.pen_down()
        self.assertEqual(command_count, len(self.io.servo_commands))

        self.plotter.pen_up()
        up_commands = self.io.servo_commands[command_count:-1]
        self.assertEqual(vplotter.SERVO_UP_US, up_commands[-1])
        self.assertEqual(0, self.io.servo_commands[-1])
        self.assertTrue(all(
            (b - a) * down_direction < 0
            for a, b in zip(up_commands, up_commands[1:])
        ))
        self.assertEqual(vplotter.SERVO_UP_US, self.plotter.servo_us)

    def test_final_zone_uses_slow_step_limit(self):
        self.plotter.pen_down()
        commands = self.io.servo_commands[2:-1]
        distance = abs(vplotter.SERVO_DOWN_US - vplotter.SERVO_UP_US)
        slow_distance = distance * vplotter.SERVO_SLOW_ZONE
        slow_commands = [
            command for command in commands
            if abs(vplotter.SERVO_DOWN_US - command) <= slow_distance
        ]

        self.assertGreater(len(slow_commands), 1)
        self.assertTrue(all(
            abs(b - a) <= vplotter.SERVO_SLOW_STEP_US
            for a, b in zip(slow_commands, slow_commands[1:])
        ))

    def test_lgpio_servo_stop_is_not_sent_twice(self):
        io = object.__new__(vplotter.LgpioIO)
        io.lg = FakeLgpio()
        io.h = 1
        io.servo_active = False

        io.servo(1500)
        io.servo(0)
        io.servo(0)

        self.assertEqual(['servo', 'pwm'], [name for name, _ in io.lg.calls])
        self.assertEqual((0, 0), io.lg.calls[-1][1][-2:])


if __name__ == '__main__':
    unittest.main()