# DSA practice lab

This isolated Python lab provides one reference implementation for several checklist patterns. It is deliberately outside the OpsBridge product services: it gives you a place to study and practice interview concepts without creating another production dependency.

| Checklist concepts | Example |
|---|---|
| Arrays, strings, hash maps, two pointers/sliding window | `two_sum`, `two_pointer_pair_sum`, `longest_unique_substring_length` |
| Sorting and binary search | `merge_sort`, `binary_search` |
| Linked lists, stacks | `reverse_linked_list`, `valid_brackets` |
| Trees, queues, graphs, BFS | `level_order`, `shortest_path_length` |
| Heaps and hash maps | `top_k_frequent` |
| Tries | `Trie` |
| Recursion, backtracking, dynamic programming | `subsets`, `coin_change_minimum` |
| Big O | Complexity is documented next to each solution |

Run the standard-library tests from the repository root:

```powershell
python -m unittest practice.dsa.test_solutions -v
```

For each problem, cover the solution, solve it without assistance, say the loop invariant/correctness argument aloud, state time and space complexity, and test empty, singleton, duplicate, malformed, and unreachable inputs. Then compare your version with this reference and use AI to generate counterexamples. Passing these tests shows only that the reference implementation works; it does not establish independent interview skill. Track your own unaided attempts and mock-interview feedback in `docs/interview-prep-map.md`.
