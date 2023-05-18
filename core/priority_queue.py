import heapq
from typing import TypeVar, Optional, List, Iterator, Generic

T = TypeVar('T')
class PriorityQueue(Generic[T]):

    def __init__(self, items: Optional[List[T]] = None):
        self._minHeap: List[T] = items if items else list()
        heapq.heapify(self._minHeap)

    def poll(self) -> T:
        self._assert_non_empty()
        return heapq.heappop(self._minHeap)


    def offer(self, element: T) -> None:
        heapq.heappush(self._minHeap, element)

    def peek(self) -> T:
        self._assert_non_empty()
        return self._minHeap[0]

    def isEmpty(self) -> bool:
        return len(self) == 0

    def _assert_non_empty(self) -> None:
        if self.isEmpty():
            raise ValueError("Queue is empty.")

    def __len__(self) -> int:
        return len(self._minHeap)

    def __iter__(self) -> Iterator[T]:
        return self._minHeap.__iter__()

    def __repr__(self) -> str:
        return f"PriorityQueue[{', '.join(self._minHeap)}]"
