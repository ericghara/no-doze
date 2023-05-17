from unittest import TestCase

from src.priority_queue import PriorityQueue


class TestPriorityQueue(TestCase):

    def test_constructor_no_args(self):
        pq = PriorityQueue()
        self.assertTrue(pq.isEmpty())

    def test_poll(self):
        pq = PriorityQueue([2,1])
        self.assertEqual(1, pq.poll() )

    def test_poll_raises(self):
        pq = PriorityQueue()
        self.assertRaises(ValueError, lambda: pq.poll() )

    def test_offer(self):
        pq = PriorityQueue([2])
        pq.offer(1)
        self.assertEqual(1, pq.peek() )

    def test_peek_raises(self):
        pq = PriorityQueue()
        self.assertRaises(ValueError, lambda: pq.peek() )

    def test_is_empty(self):
        pq = PriorityQueue()
        self.assertTrue(pq.isEmpty())

    def test_len(self):
        pq = PriorityQueue([1,2,3])
        self.assertEqual(3, len(pq) )

    def test_iter(self):
        pq = PriorityQueue([1,2,3])
        # note by definition an ordered sequence is a min heap
        # slightly fragile test assuming a valid heap input is not re-ordered on heapification
        self.assertEqual([1,2,3], [*pq])

