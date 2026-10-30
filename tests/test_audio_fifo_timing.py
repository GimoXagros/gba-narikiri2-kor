"""Analytical boundary checks for the documented private mGBA reference fix."""
import unittest


def first_sample(sample_event, dispatched_at, lateness, resolution, corrected):
    interval = 1 << (9 - resolution)
    until = sample_event - dispatched_at - 1 + (lateness if corrected else 0)
    return (2 << resolution) - min(2 << resolution, (until + interval) // interval)


class AudioFifoTimingTests(unittest.TestCase):
    def test_observed_timer_boundary_and_channel_delta(self):
        event, scheduled = 232189952, 232189692
        self.assertEqual(first_sample(event, scheduled + 1, 1, 1, False), 2)
        self.assertEqual(first_sample(event, scheduled + 4, 4, 1, False), 3)
        self.assertEqual(first_sample(event, scheduled + 1, 1, 1, True), 2)
        self.assertEqual(first_sample(event, scheduled + 4, 4, 1, True), 2)
        self.assertEqual(((-5 - -2) * 4 * 48, (-11 - -10) * 4 * 48), (-576, -192))

    def test_scheduled_position_is_invariant_to_dispatch_lateness(self):
        for resolution in range(4):
            for phase in range(1, 1025):
                expected = first_sample(4096, 4096-phase, 0, resolution, False)
                for late in (0, 1, 3, 4, 7, 31):
                    self.assertEqual(first_sample(4096, 4096-phase+late, late, resolution, True), expected)


if __name__ == '__main__':
    unittest.main()
