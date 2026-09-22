"""Offline provenance and admission proofs; no CLI/model/guard setup calls."""
import copy
import importlib.util
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[3]
ADDON = Path(__file__).resolve().parents[1]
BASE = PROJECT / 'work/fable-reconcile-2026-09-22'
RETURN = PROJECT / 'outputs/fable-e3-complete-review-2026-09-22/extracted/bundle-stage-records'


def clone_tree(source: Path, target: Path) -> None:
    if sys.platform == 'darwin':
        subprocess.run(['cp', '-c', '-R', str(source), str(target)], check=True)
    else:
        shutil.copytree(source, target)


class E8AddonOffline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('e8_addon_test', ADDON / 'tools/e8_resume.py')
        cls.tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.tool)
        cls.common = cls.tool.trusted_common(BASE / 'supplement')
        cls.validator = cls.common.Validator(BASE / 'fixture-repo')
        cls.temp = tempfile.TemporaryDirectory(prefix='fable-e8-offline-')
        cls.bundle = (Path(cls.temp.name) / 'bundle').resolve()
        clone_tree(BASE / 'fixture/fable-resume-corrected-2026-09-20', cls.bundle)
        shutil.copytree(RETURN, cls.bundle / 'stages', dirs_exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_completed_e3_admits_only_the_frozen_e8_missing_panel(self):
        index, status = self.tool.admit(self.bundle, self.common, self.validator)
        self.assertEqual((len(index['reused_main_slots']), status['complete'], len(status['missing'])), (140, 0, 160))
        self.assertEqual(sum(p['slot_kind'] == 'main' for p in index['packets']), 140)
        self.assertEqual(sum(p['slot_kind'] == 'duplicate' for p in index['packets']), 20)

    def test_original_aapl_stop_cannot_be_changed_or_ignored(self):
        path = self.bundle / 'stages/e3-candidate1/STOP.json'
        original = path.read_bytes()
        try:
            path.write_bytes(original + b'\n')
            with self.assertRaisesRegex(ValueError, 'Original STOP missing or changed'):
                self.tool.admit(self.bundle, self.common, self.validator)
        finally:
            path.write_bytes(original)

    def test_missing_completed_e3_output_refuses_e8(self):
        path = next((self.bundle / 'stages/e3-candidate2/slots').glob('*/judged.json'))
        original = path.read_bytes()
        try:
            path.unlink()
            with self.assertRaisesRegex(ValueError, 'Completed ledger output is missing'):
                self.tool.admit(self.bundle, self.common, self.validator)
        finally:
            path.write_bytes(original)

    def test_unlogged_valid_looking_e8_output_is_not_admitted(self):
        index = self.common.load_index(self.bundle, 'e8')
        entry = index['packets'][0]
        output = json.loads(Path(entry['packet_path']).read_text())
        _, lengths, _ = self.validator._context(output['results'][0])
        output['harness'].update(judge='cli:claude-fable-5-1', judge_contract_version=2)
        output['results'][0]['judge'] = {'error': None, 'input_complete': True,
            'contract_version': 2, 'verdict': 'PASS', 'passed': True,
            'dimensions': {'faithfulness': 4, 'insight': 4, 'clarity': 4, 'specificity': 4},
            'mean_dimension': 4, 'gate_failures': [], 'input_lengths': lengths}
        self.validator.validate_output(entry, output)
        slot = self.bundle / 'stages/e8/slots' / entry['slot']
        slot.mkdir(parents=True)
        try:
            (slot / 'judged.json').write_text(json.dumps(output))
            with self.assertRaisesRegex(ValueError, 'no immutable or execution-ledger provenance'):
                self.tool.admit(self.bundle, self.common, self.validator)
        finally:
            shutil.rmtree(slot)

    def test_e8_stop_and_changed_order_refuse_admission(self):
        stop = self.bundle / 'stages/e8/STOP.supplement.json'
        try:
            stop.write_text('{}\n')
            with self.assertRaisesRegex(ValueError, 'E8 STOP or pending'):
                self.tool.admit(self.bundle, self.common, self.validator)
        finally:
            stop.unlink()
        original = self.common.load_index
        def changed(root, stage):
            index = original(root, stage)
            index['packets'][0]['order'] = 300
            return index
        self.common.load_index = changed
        try:
            with self.assertRaisesRegex(ValueError, 'frozen order changed'):
                self.tool.verify_panel(self.bundle, self.common, self.validator)
        finally:
            self.common.load_index = original

    def test_inter_slot_stop_and_prerequisite_change_block_next_pending(self):
        index, status = self.tool.admit(self.bundle, self.common, self.validator)
        missing = status['missing']
        self.tool.admit_next_slot(self.bundle, self.common, self.validator, missing, index['packets'][0]['slot'])
        stop = self.bundle / 'stages/e8/STOP.supplement.json'
        try:
            stop.write_text('{}\n')
            with self.assertRaisesRegex(ValueError, 'E8 STOP or pending'):
                self.tool.admit_next_slot(self.bundle, self.common, self.validator, missing, index['packets'][1]['slot'])
            self.assertEqual(list((self.bundle / 'stages/e8').glob('.pending-*')), [])
        finally:
            stop.unlink()
        prior = next((self.bundle / 'stages/e3-candidate2/slots').glob('*/judged.json'))
        original = prior.read_bytes()
        try:
            prior.unlink()
            with self.assertRaisesRegex(ValueError, 'Completed ledger output is missing'):
                self.tool.admit_next_slot(self.bundle, self.common, self.validator, missing, index['packets'][1]['slot'])
            self.assertEqual(list((self.bundle / 'stages/e8').glob('.pending-*')), [])
        finally:
            prior.write_bytes(original)

    def test_remote_guard_setup_is_a_hard_hold(self):
        attestation = Path(self.temp.name) / 'synthetic-attestation.json'
        guard = self.bundle / 'e8/guard'
        attestation.write_text(json.dumps({
            'schema': 'fable-e8-accounting-attestation-v1', 'operator': 'offline-test',
            'observed_at_utc': datetime.now(timezone.utc).isoformat(), 'prior_count': 287,
            'prior_evidence_sha256': self.tool.PRIOR_EVIDENCE_SHA256,
            'founder_statement_sha256': self.tool.FOUNDER_STATEMENT_SHA256,
            'original_manifest_sha256': self.tool.ORIGINAL_MANIFEST_SHA256,
            'e3_supplement_manifest_sha256': self.tool.E3_SUPPLEMENT_MANIFEST_SHA256,
            'guard_state_path': str(guard / 'state.json'),
            'no_untracked_e8_or_probe_calls': True, 'sole_persistent_guard': True,
            'exclusive_e8_dispatch_during_continuation': True,
        }))
        with self.assertRaisesRegex(ValueError, 'has not completed one-time initialization'):
            self.tool.attest(self.bundle, guard, attestation, self.common)

    def test_synthetic_counter_rejects_an_unrecorded_call(self):
        # Logical continuity proof only: no original guard file or CLI is touched.
        fake_dir = (Path(self.temp.name) / 'synthetic-counter').resolve()
        fake_dir.mkdir()
        state_path = fake_dir / 'state.json'
        (fake_dir / 'initialization.json').write_text(json.dumps({
            'status': 'complete', 'prior_count': 287, 'state_path': str(state_path)}))
        attestation = fake_dir / 'attestation.json'
        attestation.write_text(json.dumps({
            'schema': 'fable-e8-accounting-attestation-v1', 'operator': 'offline-test',
            'observed_at_utc': datetime.now(timezone.utc).isoformat(), 'prior_count': 287,
            'prior_evidence_sha256': self.tool.PRIOR_EVIDENCE_SHA256,
            'founder_statement_sha256': self.tool.FOUNDER_STATEMENT_SHA256,
            'original_manifest_sha256': self.tool.ORIGINAL_MANIFEST_SHA256,
            'e3_supplement_manifest_sha256': self.tool.E3_SUPPLEMENT_MANIFEST_SHA256,
            'guard_state_path': str(state_path),
            'no_untracked_e8_or_probe_calls': True, 'sole_persistent_guard': True,
            'exclusive_e8_dispatch_during_continuation': True,
        }))
        state = {'real_cli_invocations': 287, 'completed': []}
        fake_common = SimpleNamespace(validate_guard=lambda _: ({'state_path': str(state_path), 'ceiling': 601}, state))
        self.tool.attest(self.bundle, fake_dir, attestation, fake_common)
        state['real_cli_invocations'] = 288
        state['completed'] = [{'invocation': 288}]
        ledger = self.bundle / 'stages/e8/execution-ledger.supplement.jsonl'
        try:
            ledger.write_text(json.dumps({'guard_before': {'real_cli_invocations': 287},
                                         'guard_after': {'real_cli_invocations': 288}}) + '\n')
            self.tool.attest(self.bundle, fake_dir, attestation, fake_common)
            state['real_cli_invocations'] = 289
            state['completed'].append({'invocation': 289})
            with self.assertRaisesRegex(ValueError, 'unaccounted calls'):
                self.tool.attest(self.bundle, fake_dir, attestation, fake_common)
        finally:
            ledger.unlink(missing_ok=True)

    def test_two_successful_synthetic_slots_advance_queue(self):
        # Exercise execute's real loop with a fake in-process harness and guard snapshots.
        # Neither the frozen harness nor the real CLI is started.
        bundle = (Path(self.temp.name) / 'two-slot-bundle').resolve()
        clone_tree(self.bundle, bundle)
        index, status = self.tool.admit(bundle, self.common, self.validator)
        attestation = Path(self.temp.name) / 'two-slot-synthetic-attestation.txt'
        attestation.write_text('offline test fixture; not an operator attestation\n')
        guard = bundle / 'e8/guard'
        cfg = {'real_cli': '/usr/bin/true', 'state_path': str(guard / 'state.json'), 'ceiling': 601}
        state = {'real_cli_invocations': 287, 'completed': [], 'active': {}, 'stop_reason': None}
        output_count = []
        original_read = self.tool.read
        def fake_read(path):
            path = Path(path)
            if path == guard / 'state.json':
                return copy.deepcopy(state)
            if path == guard / 'config.json':
                return copy.deepcopy(cfg)
            return original_read(path)
        def fake_attest(*_args, **_kwargs):
            return copy.deepcopy(cfg), copy.deepcopy(state)
        validator = self.validator
        class FakePopen:
            def __init__(self, cmd, **_kwargs):
                self.pid = 91000 + len(output_count)
                self.returncode = 0
                packet = json.loads(Path(cmd[3]).read_text())
                _, lengths, _ = validator._context(packet['results'][0])
                packet['harness'].update(judge='cli:claude-fable-5-1', judge_contract_version=2)
                packet['results'][0]['judge'] = {'error': None, 'input_complete': True,
                    'contract_version': 2, 'verdict': 'PASS', 'passed': True,
                    'dimensions': {'faithfulness': 4, 'insight': 4, 'clarity': 4, 'specificity': 4},
                    'mean_dimension': 4, 'gate_failures': [], 'input_lengths': lengths}
                pending = Path(cmd[cmd.index('--output-dir') + 1])
                (pending / 'judged.json').write_text(json.dumps(packet))
                state['real_cli_invocations'] += 1
                state['completed'].append({'invocation': state['real_cli_invocations'],
                                           'quota': False, 'owner_lost': False})
                output_count.append(pending.name)
            def communicate(self):
                return ('synthetic local harness output', '')
        args = SimpleNamespace(python=Path(sys.executable), cli=Path('/usr/bin/true'),
            guard_dir=guard, attestation=attestation, max_new=2, repo=BASE / 'fixture-repo')
        with patch.object(self.tool, 'read', fake_read), \
             patch.object(self.tool, 'attest', fake_attest), \
             patch.object(self.common, 'verified_cli', return_value=(Path('/usr/bin/true'), '2.1.278 (synthetic)')), \
             patch.object(self.tool.shutil, 'which', return_value=str(guard / 'claude')), \
             patch.object(self.tool.subprocess, 'Popen', FakePopen):
            result = self.tool.execute(args, bundle, self.common, self.validator)
        self.assertEqual(result, 0)
        self.assertEqual(len(output_count), 2)
        self.assertEqual(state['real_cli_invocations'], 289)
        rows = [json.loads(line) for line in (bundle / 'stages/e8/execution-ledger.supplement.jsonl').read_text().splitlines()]
        self.assertEqual([row['slot'] for row in rows], [p['slot'] for p in index['packets'][:2]])
        self.assertEqual([row['guard_after']['real_cli_invocations'] for row in rows], [288, 289])
        self.assertEqual(len(self.tool.admit(bundle, self.common, self.validator)[1]['missing']), 158)
        self.assertFalse((bundle / 'stages/e8/STOP.supplement.json').exists())

    def test_attestation_time_must_be_fresh_utc(self):
        fixed = datetime(2026, 9, 22, 12, 0, tzinfo=timezone.utc)
        guard = self.bundle / 'e8/guard'
        path = Path(self.temp.name) / 'time-attestation.json'
        base = {
            'schema': 'fable-e8-accounting-attestation-v1', 'operator': 'offline-test',
            'prior_count': 287, 'prior_evidence_sha256': self.tool.PRIOR_EVIDENCE_SHA256,
            'founder_statement_sha256': self.tool.FOUNDER_STATEMENT_SHA256,
            'original_manifest_sha256': self.tool.ORIGINAL_MANIFEST_SHA256,
            'e3_supplement_manifest_sha256': self.tool.E3_SUPPLEMENT_MANIFEST_SHA256,
            'guard_state_path': str(guard / 'state.json'),
            'no_untracked_e8_or_probe_calls': True, 'sole_persistent_guard': True,
            'exclusive_e8_dispatch_during_continuation': True,
        }
        for timestamp, expected in (
            ('nonsense', 'malformed'),
            ('2026-09-22T12:00:00+01:00', 'must be UTC'),
            ((fixed - timedelta(hours=6, seconds=1)).isoformat(), 'expired or is future-dated'),
            ((fixed + timedelta(minutes=5, seconds=1)).isoformat(), 'expired or is future-dated'),
        ):
            path.write_text(json.dumps(dict(base, observed_at_utc=timestamp)))
            with self.assertRaisesRegex(ValueError, expected):
                self.tool.attest(self.bundle, guard, path, self.common, observed_now=fixed)
        for timestamp in ((fixed - timedelta(hours=6)).isoformat(),
                          (fixed + timedelta(minutes=5)).isoformat()):
            path.write_text(json.dumps(dict(base, observed_at_utc=timestamp)))
            with self.assertRaisesRegex(ValueError, 'has not completed one-time initialization'):
                self.tool.attest(self.bundle, guard, path, self.common, observed_now=fixed)


if __name__ == '__main__':
    unittest.main()
