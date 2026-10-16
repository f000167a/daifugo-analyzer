"""Regression checks for the corresponding rule fixes in the optional trainer."""
import random
import unittest
import train


class TrainingRulesTest(unittest.TestCase):
    def test_joker_is_strictly_highest(self):
        for rev in (False, True):
            for rank in range(3, 16):
                self.assertGreater(train.rk(16, rev), train.rk(rank, rev))
            self.assertIsNone(train.pick({16: 1}, [16, 1], rev, [1, 1], True, train.W_INIT))

    def test_complements_can_lead(self):
        self.assertEqual(train.move_sizes(1, 2, None), [(1, 0), (2, 1), (3, 2)])
        self.assertIn((4, 1), train.move_sizes(3, 1, None))

    def test_balanced_conservation_and_termination(self):
        deck = [n for n in range(3, 16) for _ in range(4)] + [16, 16]
        for count, size in [(3, 18), (4, 13), (4, 14), (5, 10), (5, 11)]:
            for seed in range(20):
                random.seed(seed)
                random.shuffle(deck)
                hand = {n: deck[:size].count(n) for n in train.NUMS}
                original = dict(hand)
                players = train.deal_hands(hand, count)
                self.assertEqual(players[0], hand)
                self.assertEqual(sum(map(train.hand_sum, players)), 54)
                for player in players:
                    self.assertIn(train.hand_sum(player), {54 // count, (54 + count - 1) // count})
                for rank in train.NUMS:
                    self.assertEqual(sum(h[rank] for h in players), 2 if rank == 16 else 4)
                for r8 in (False, True):
                    for rev in (False, True):
                        rank = train.sim_once(hand, count, r8, rev, train.W_INIT)
                        self.assertIn(rank, range(1, count + 1))
                self.assertEqual(hand, original)

    def test_invalid_hands(self):
        for hand, count in [({}, 3), ({16: 3}, 3), ({3: -1}, 3), ({3: 1.5}, 3), ({17: 1}, 3), ({}, 2)]:
            with self.assertRaises(ValueError):
                train.deal_hands(hand, count)


if __name__ == '__main__':
    unittest.main()
