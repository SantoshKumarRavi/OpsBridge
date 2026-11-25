import unittest

from practice.dsa.solutions import (
    ListNode,
    TreeNode,
    Trie,
    binary_search,
    coin_change_minimum,
    level_order,
    longest_unique_substring_length,
    merge_sort,
    reverse_linked_list,
    shortest_path_length,
    subsets,
    top_k_frequent,
    two_sum,
    two_pointer_pair_sum,
    valid_brackets,
)


class ArrayAndStringTests(unittest.TestCase):
    def test_two_sum_handles_duplicates_and_no_solution(self):
        self.assertEqual(two_sum([3, 3], 6), (0, 1))
        self.assertEqual(two_sum([2, 7, 11], 9), (0, 1))
        self.assertIsNone(two_sum([], 5))

    def test_two_pointer_pair_sum_requires_sorted_input_and_distinct_indices(self):
        self.assertEqual(two_pointer_pair_sum([-3, 1, 4, 8], 5), (0, 3))
        self.assertIsNone(two_pointer_pair_sum([2], 4))
        self.assertEqual(two_pointer_pair_sum([2, 2], 4), (0, 1))

    def test_sliding_window_handles_empty_and_repeated_prefix(self):
        self.assertEqual(longest_unique_substring_length(""), 0)
        self.assertEqual(longest_unique_substring_length("abba"), 2)
        self.assertEqual(longest_unique_substring_length("pwwkew"), 3)

    def test_binary_search_empty_missing_and_duplicate_values(self):
        self.assertEqual(binary_search([], 2), -1)
        self.assertEqual(binary_search([1, 3, 5, 7], 5), 2)
        self.assertIn(binary_search([1, 2, 2, 2, 4], 2), {1, 2, 3})
        self.assertEqual(binary_search([1, 3, 5], 2), -1)

    def test_merge_sort_is_stable_for_values_and_does_not_mutate_input(self):
        values = [4, 1, 3, 1, -2]
        self.assertEqual(merge_sort(values), [-2, 1, 1, 3, 4])
        self.assertEqual(values, [4, 1, 3, 1, -2])
        self.assertEqual(merge_sort([]), [])

    def test_top_k_frequency_order_and_invalid_k(self):
        self.assertEqual(top_k_frequent([4, 4, 1, 1, 3], 2), [1, 4])
        self.assertEqual(top_k_frequent([9, 9], 0), [])
        with self.assertRaises(ValueError):
            top_k_frequent([1], 2)


class DataStructureTests(unittest.TestCase):
    def test_reverse_linked_list_empty_and_nonempty(self):
        self.assertIsNone(reverse_linked_list(None))
        head = ListNode(1, ListNode(2, ListNode(3)))
        result = reverse_linked_list(head)
        values = []
        while result:
            values.append(result.value)
            result = result.next
        self.assertEqual(values, [3, 2, 1])

    def test_bracket_stack_rejects_mismatch_and_non_bracket_input(self):
        self.assertTrue(valid_brackets("{[()]}"))
        self.assertTrue(valid_brackets(""))
        self.assertFalse(valid_brackets("([)]"))
        self.assertFalse(valid_brackets("a"))

    def test_tree_breadth_first_levels_and_empty_tree(self):
        root = TreeNode(1, TreeNode(2, TreeNode(4)), TreeNode(3))
        self.assertEqual(level_order(root), [[1], [2, 3], [4]])
        self.assertEqual(level_order(None), [])

    def test_graph_bfs_shortest_path_and_unreachable_target(self):
        graph = {"a": ["b", "c"], "b": ["d"], "c": ["d"], "x": []}
        self.assertEqual(shortest_path_length(graph, "a", "d"), 2)
        self.assertEqual(shortest_path_length(graph, "a", "x"), -1)
        self.assertEqual(shortest_path_length(graph, "x", "x"), 0)

    def test_trie_distinguishes_words_from_prefixes(self):
        trie = Trie()
        trie.insert("care")
        trie.insert("case")
        trie.insert("")
        self.assertTrue(trie.search("care"))
        self.assertFalse(trie.search("car"))
        self.assertTrue(trie.starts_with("car"))
        self.assertTrue(trie.search(""))


class DynamicProgrammingTests(unittest.TestCase):
    def test_coin_change_minimum_and_unreachable_amount(self):
        self.assertEqual(coin_change_minimum([1, 2, 5], 11), 3)
        self.assertEqual(coin_change_minimum([2], 3), -1)
        self.assertEqual(coin_change_minimum([], 0), 0)
        with self.assertRaises(ValueError):
            coin_change_minimum([0, 1], 3)

    def test_backtracking_subsets_returns_each_choice_once(self):
        self.assertEqual(subsets([]), [[]])
        result = subsets([1, 2])
        self.assertEqual(len(result), 4)
        self.assertEqual({tuple(row) for row in result}, {(), (1,), (2,), (1, 2)})


if __name__ == "__main__":
    unittest.main()
