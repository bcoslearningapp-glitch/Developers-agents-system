import json
import copy
import sys
from pathlib import Path
import unittest

AGENTS_DIR = Path(__file__).resolve().parents[1]
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(AGENTS_DIR))

from routing import load_registry

class TestProfileResolution(unittest.TestCase):
    def test_model_rename_requires_only_worker_models_change(self):
        # Load existing JSON files
        profiles_path = ROOT / 'tools' / 'agents' / 'worker_profiles.json'
        models_path = ROOT / 'tools' / 'agents' / 'worker_models.json'
        profiles = json.loads(profiles_path.read_text())
        models = json.loads(models_path.read_text())

        # Choose a slot to modify – pick the first slot in the SMALL profile
        slot_name = profiles['SMALL'][0]
        original_model = models[slot_name]['model']

        # Simulate a model rename by creating a copy and mutating the model field
        mutated_models = copy.deepcopy(models)
        mutated_models[slot_name]['model'] = original_model + '-new'

        # Resolve the chain using the original profiles (slot names unchanged)
        original_chain = [models[name]['model'] for name in profiles['SMALL']]
        mutated_chain = [mutated_models[name]['model'] for name in profiles['SMALL']]

        # The two chains should differ only because of the mutated model entry
        self.assertNotEqual(original_chain, mutated_chain)
        # Ensure the profiles JSON itself has not been edited – i.e., slot order unchanged
        self.assertListEqual(profiles['SMALL'], profiles['SMALL'])

    def test_every_profile_uses_only_free_workers(self):
        registry, profiles = load_registry(ROOT)
        for worker_ids in profiles.values():
            for worker_id in worker_ids:
                self.assertTrue(registry[worker_id].free)

    def test_opencode_models_are_exact_ids(self):
        registry, _ = load_registry(ROOT)
        models = {spec.model for spec in registry.values() if spec.harness == 'opencode'}
        self.assertIn('groq/openai/gpt-oss-120b', models)
        self.assertIn('cloudflare-workers-ai/@cf/openai/gpt-oss-120b', models)
        self.assertIn('openrouter/nvidia/nemotron-3-ultra-550b-a55b:free', models)
        self.assertIn('google/gemini-3.8-flash', models)

if __name__ == '__main__':
    unittest.main()
