import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import hybrid_search as search
from benchmarks.benchmark import evaluate_hybrid


class RetrievalTests(unittest.TestCase):
    def test_backend_failure_is_not_a_miss(self):
        for response in [subprocess.CompletedProcess([], 1, '', 'error'),
                         subprocess.CompletedProcess([], 0, '', ''),
                         subprocess.CompletedProcess([], 0, '{bad', '')]:
            with self.subTest(response=response), patch.object(search.subprocess, 'run', return_value=response):
                with self.assertRaises(RuntimeError):
                    search.run_single_search('grepai', '.', 'query')

    def test_timeout_is_reported(self):
        with patch.object(search.subprocess, 'run', side_effect=subprocess.TimeoutExpired('grepai', 60)):
            with self.assertRaises(RuntimeError):
                search.run_single_search('grepai', '.', 'query')

    def test_empty_json_results_are_valid(self):
        with patch.object(search.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '[]', '')):
            self.assertEqual(search.run_single_search('grepai', '.', 'query'), [])

    def test_project_boundaries_and_explicit_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'workspaces').mkdir()
            registry = {'app': {'source_path': str(root / 'app'), 'text_dir': 'text', 'code_dir': 'code'}}
            (root / 'workspaces/registry.json').write_text(json.dumps(registry))
            with patch.object(search, '__file__', str(root / 'hybrid_search.py')):
                self.assertEqual(search.resolve_project_dirs(project_path=str(root / 'app/src'))[2], 'app')
                for target in [str(root / 'app-other'), 'misspelled']:
                    with self.assertRaises(ValueError):
                        search.resolve_project_dirs(project=target)
                self.assertEqual(search.resolve_project_dirs(text_dir='a', code_dir='b'), ('a', 'b', 'explicit'))

    def test_fusion_ties_are_deterministic(self):
        a = {'file_path': 'a.py'}
        b = {'file_path': 'b.py'}
        result = search.reciprocal_rank_fusion([b], [a], weight_code=1, weight_text=1)
        self.assertEqual([r['file_path'] for r in result], ['a.py', 'b.py'])

    def test_hybrid_metrics_respect_result_limit(self):
        results = [{'file_path': 'a.py'}, {'file_path': 'b.py'}]
        with patch('benchmarks.benchmark.run_grepai_search', return_value=(results, 1)):
            metrics = evaluate_hybrid('grepai', '.', '.', [{'query': 'q', 'expected_file': 'b.py'}], limit=1)
        self.assertEqual(metrics['mrr'], 0)


if __name__ == '__main__':
    unittest.main()
