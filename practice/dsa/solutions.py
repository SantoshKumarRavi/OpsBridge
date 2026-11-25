"""Small, explained implementations for common interview patterns.

These are study examples. Each docstring states expected complexity and the
input assumptions that matter for explaining correctness in an interview.
"""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, field
import heapq
from typing import Hashable, Iterable, TypeVar


Node = TypeVar("Node", bound=Hashable)


def two_sum(values: list[int], target: int) -> tuple[int, int] | None:
    """Return distinct matching indices, if any. O(n) time and O(n) space."""
    seen: dict[int, int] = {}
    for index, value in enumerate(values):
        complement = target - value
        if complement in seen:
            return seen[complement], index
        seen[value] = index
    return None


def two_pointer_pair_sum(sorted_values: list[int], target: int) -> tuple[int, int] | None:
    """Find a pair in ascending input. O(n) time and O(1) extra space."""
    left, right = 0, len(sorted_values) - 1
    while left < right:
        total = sorted_values[left] + sorted_values[right]
        if total == target:
            return left, right
        if total < target:
            left += 1
        else:
            right -= 1
    return None


def longest_unique_substring_length(text: str) -> int:
    """Longest substring without repeated characters. O(n) time and O(k) space."""
    last_seen: dict[str, int] = {}
    left = best = 0
    for right, character in enumerate(text):
        previous = last_seen.get(character, -1)
        if previous >= left:
            left = previous + 1
        last_seen[character] = right
        best = max(best, right - left + 1)
    return best


def binary_search(sorted_values: list[int], target: int) -> int:
    """Find one target index in ascending input. O(log n) time, O(1) space."""
    low, high = 0, len(sorted_values) - 1
    while low <= high:
        middle = low + (high - low) // 2
        if sorted_values[middle] == target:
            return middle
        if sorted_values[middle] < target:
            low = middle + 1
        else:
            high = middle - 1
    return -1


def merge_sort(values: list[int]) -> list[int]:
    """Stable merge sort. O(n log n) time and O(n) auxiliary space."""
    if len(values) < 2:
        return values.copy()
    middle = len(values) // 2
    left = merge_sort(values[:middle])
    right = merge_sort(values[middle:])
    merged: list[int] = []
    i = j = 0
    while i < len(left) and j < len(right):
        if left[i] <= right[j]:
            merged.append(left[i])
            i += 1
        else:
            merged.append(right[j])
            j += 1
    merged.extend(left[i:])
    merged.extend(right[j:])
    return merged


@dataclass
class ListNode:
    value: int
    next: ListNode | None = None


def reverse_linked_list(head: ListNode | None) -> ListNode | None:
    """Reverse a singly linked list in place. O(n) time and O(1) space."""
    previous = None
    current = head
    while current is not None:
        following = current.next
        current.next = previous
        previous, current = current, following
    return previous


def valid_brackets(text: str) -> bool:
    """Validate bracket nesting. O(n) time and O(n) worst-case space."""
    opening = {"(": ")", "[": "]", "{": "}"}
    closers = set(opening.values())
    stack: list[str] = []
    for character in text:
        if character in opening:
            stack.append(opening[character])
        elif character in closers:
            if not stack or stack.pop() != character:
                return False
        else:
            return False
    return not stack


@dataclass
class TreeNode:
    value: int
    left: TreeNode | None = None
    right: TreeNode | None = None


def level_order(root: TreeNode | None) -> list[list[int]]:
    """Return binary-tree levels using BFS. O(n) time and O(w) queue space."""
    if root is None:
        return []
    result: list[list[int]] = []
    queue = deque([root])
    while queue:
        level: list[int] = []
        for _ in range(len(queue)):
            node = queue.popleft()
            level.append(node.value)
            if node.left:
                queue.append(node.left)
            if node.right:
                queue.append(node.right)
        result.append(level)
    return result


def shortest_path_length(graph: dict[Node, Iterable[Node]], start: Node, goal: Node) -> int:
    """Shortest unweighted path length by BFS; return -1 when unreachable.

    O(V + E) time and O(V) space for the reachable subgraph.
    """
    if start == goal:
        return 0
    distances = {start: 0}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        for neighbor in graph.get(node, ()):
            if neighbor in distances:
                continue
            distances[neighbor] = distances[node] + 1
            if neighbor == goal:
                return distances[neighbor]
            queue.append(neighbor)
    return -1


def top_k_frequent(values: list[int], k: int) -> list[int]:
    """Return k most frequent values with deterministic ties.

    O(n + u log k) time and O(u + k) space, where u is the number of unique
    values. Equal frequencies are ordered by ascending value.
    """
    if k < 0:
        raise ValueError("k must be non-negative")
    counts = Counter(values)
    if k > len(counts):
        raise ValueError("k cannot exceed the number of unique values")
    return [value for value, _ in heapq.nsmallest(k, counts.items(), key=lambda row: (-row[1], row[0]))]


@dataclass
class TrieNode:
    children: dict[str, TrieNode] = field(default_factory=dict)
    terminal: bool = False


class Trie:
    """Prefix tree with O(m) insert/search/prefix checks for word length m."""

    def __init__(self) -> None:
        self.root = TrieNode()

    def insert(self, word: str) -> None:
        node = self.root
        for character in word:
            node = node.children.setdefault(character, TrieNode())
        node.terminal = True

    def search(self, word: str) -> bool:
        node = self._walk(word)
        return node is not None and node.terminal

    def starts_with(self, prefix: str) -> bool:
        return self._walk(prefix) is not None

    def _walk(self, text: str) -> TrieNode | None:
        node = self.root
        for character in text:
            node = node.children.get(character)
            if node is None:
                return None
        return node


def coin_change_minimum(coins: list[int], amount: int) -> int:
    """Minimum coins for an unbounded coin set; -1 if impossible.

    O(amount * len(coins)) time and O(amount) space. Coin values must be
    positive; amount must be non-negative.
    """
    if amount < 0:
        raise ValueError("amount must be non-negative")
    if any(coin <= 0 for coin in coins):
        raise ValueError("coin values must be positive")
    best = [0] + [amount + 1] * amount
    for subtotal in range(1, amount + 1):
        best[subtotal] = min(
            (best[subtotal - coin] + 1 for coin in coins if coin <= subtotal),
            default=amount + 1,
        )
    return best[amount] if best[amount] <= amount else -1


def subsets(values: list[int]) -> list[list[int]]:
    """Enumerate the power set with backtracking. O(n * 2^n) output time."""
    result: list[list[int]] = []
    current: list[int] = []

    def visit(index: int) -> None:
        if index == len(values):
            result.append(current.copy())
            return
        visit(index + 1)
        current.append(values[index])
        visit(index + 1)
        current.pop()

    visit(0)
    return result
