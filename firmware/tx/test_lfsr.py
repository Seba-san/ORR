import unittest
from lfsr import LFSR

class TestLFSR(unittest.TestCase):
    """
    Test suite to verify the mathematical and statistical properties
    of the corrected PRBS-7 generator (LFSR).
    """

    def test_sequence_length(self):
        """
        Verifies that a single cycle of the PRBS-7 sequence is exactly 127 bits long.
        """
        lfsr = LFSR(seed=0x7F)
        seq = lfsr.generate_sequence()
        self.assertEqual(len(seq), 127)

    def test_statistical_balance(self):
        """
        Verifies the balance property: PRBS-7 should have exactly
        2^(n-1) = 64 ones and 2^(n-1) - 1 = 63 zeros.
        """
        lfsr = LFSR(seed=0x7F)
        seq = lfsr.generate_sequence()
        ones = sum(seq)
        zeros = 127 - ones
        self.assertEqual(ones, 64)
        self.assertEqual(zeros, 63)

    def test_periodicity(self):
        """
        Verifies that the sequence has a maximal period of 127 and repeats identically.
        """
        lfsr = LFSR(seed=0x7F)
        
        # Generate 254 bits (2 cycles) step-by-step
        seq_long = [lfsr._step() for _ in range(254)]
        
        first_cycle = seq_long[:127]
        second_cycle = seq_long[127:]
        
        self.assertEqual(first_cycle, second_cycle)

    def test_maximality_and_states(self):
        """
        Verifies that all possible 2^7 - 1 = 127 non-zero 7-bit states
        are visited exactly once during a full cycle.
        """
        lfsr = LFSR(seed=0x7F)
        visited_states = set()
        
        # Step through a full cycle and record the register state
        for _ in range(127):
            state = lfsr.state
            # Ensure the state is non-zero
            self.assertNotEqual(state, 0)
            # Ensure the state hasn't been visited yet (maximality check)
            self.assertNotIn(state, visited_states)
            visited_states.add(state)
            lfsr._step()
            
        # Ensure we visited all 127 unique non-zero states
        self.assertEqual(len(visited_states), 127)

    def test_invalid_seeds(self):
        """
        Verifies that invalid seeds (0, or values > 127) raise a ValueError.
        """
        # Seed 0 is forbidden
        with self.assertRaises(ValueError):
            LFSR(seed=0)
            
        # Seed > 127 is forbidden (only 7 bits allowed)
        with self.assertRaises(ValueError):
            LFSR(seed=128)

        with self.assertRaises(ValueError):
            LFSR(seed=0x100)

if __name__ == '__main__':
    unittest.main()
