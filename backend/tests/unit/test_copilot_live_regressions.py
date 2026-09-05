"""Regressions from the retained first 18-attempt live report; no provider calls."""
from copy import deepcopy
import os
from pathlib import Path
import subprocess

import pytest
import yaml

from app.services import copilot_service as service
from evals.copilot_schema import CopilotQACase
from evals.copilot_scorers import score_copilot_answer, score_numeric_recall
from evals.schema import GroundTruthFact
from tests.unit.test_copilot_provenance import filing


@pytest.mark.parametrize('step_prefix,log_name', [
    ('Prepare actual', 'preparation.log'), ('Run every', 'runner.log'),
])
def test_logged_workflow_propagates_actual_python_failure(tmp_path, step_prefix, log_name):
    workflow = yaml.safe_load((Path(__file__).parents[3] / '.github/workflows/copilot-eval.yml').read_text())
    step = next(s for s in workflow['jobs']['copilot-eval']['steps']
                if s.get('name', '').startswith(step_prefix))
    # Run the exact YAML command with Actions' documented explicit/default Bash semantics.
    # Only Python is stubbed; real Bash and tee must retain evidence AND propagate failure.
    executable = tmp_path / 'python'
    executable.write_text('#!/bin/sh\necho retained-public-evidence\nexit "$PROBE_EXIT"\n')
    executable.chmod(0o755)
    (tmp_path / 'evals/reports/copilot').mkdir(parents=True)
    script = tmp_path / 'step.sh'
    script.write_text(step['run'])
    command = (['bash', '--noprofile', '--norc', '-eo', 'pipefail']
               if step.get('shell') == 'bash' else ['bash', '-e'])
    for code in (0, 17):
        env = {**os.environ, 'PATH': str(tmp_path) + os.pathsep + os.environ['PATH'],
               'PROBE_EXIT': str(code), 'RUNNER_TEMP': str(tmp_path)}
        result = subprocess.run([*command, str(script)], cwd=tmp_path, env=env,
                                capture_output=True, text=True, timeout=5)
        assert result.returncode == code, (step_prefix, code, result.stdout, result.stderr)
        assert (tmp_path / 'evals/reports/copilot' / log_name).read_text() == 'retained-public-evidence\n'


@pytest.mark.parametrize('answer,expected', [
    ('Revenue for the year ended June 30, 2025 was $281,724 million, and diluted earnings per share was $13.64.', (1.0, [])),
    ('Revenue was $281,724 million, and diluted earnings per share was $13.70.', (0.5, ['eps_diluted'])),
    ('Revenue was $281,724 million.', (0.5, ['eps_diluted'])),
])
def test_actual_mixed_unit_eps_answer_and_wrong_or_missing_eps(answer, expected):
    qa = CopilotQACase(question='Revenue and diluted EPS?', expected_facts=[
        GroundTruthFact('revenue', 281724000000, 'USD'),
        GroundTruthFact('eps_diluted', 13.64, 'USD/shares'),
    ])
    original = deepcopy(qa)
    assert score_numeric_recall(answer, qa) == expected
    assert qa == original  # no canonical source/golden-unit mutation


def test_contiguous_citation_instruction_reaches_actual_service_messages():
    messages = service._build_messages(filing(), 'Filing source.', 'Revenue?', [])
    instruction = messages[0]['content']
    assert 'SHORTEST contiguous span' in instruction
    assert 'Never stitch separated table cells or sentences together, or insert an ellipsis' in instruction
    assert 'reuse its existing [F#] marker; do not add a text citation' in instruction


def test_actual_aapl_stitched_quote_remains_a_hard_veto():
    # Exact nearby rows retained in first-live AAPL inputs; the model invented the ellipsis.
    source = ('Total net sales416,161\xa0391,035\xa0383,285\xa0\n\nCost of sales:\n\n'
              '\xa0\xa0\xa0Products194,116\xa0185,233\xa0189,282\xa0\n\n'
              '\xa0\xa0\xa0Services26,844\xa025,119\xa024,855\xa0\n\n'
              'Total cost of sales220,960\xa0210,352\xa0214,137\xa0\n\n'
              'Gross margin195,201\xa0180,683\xa0169,148\xa0')
    excerpt = 'Total net sales 416,161 ... Gross margin 195,201'
    qa = CopilotQACase(question='Net sales and gross profit?', expected_facts=[
        GroundTruthFact('revenue', 416161000000, 'USD'),
        GroundTruthFact('gross_profit', 195201000000, 'USD')])
    answer = 'Total net sales were $416,161 million and gross profit was $195,201 million [1].'
    result = score_copilot_answer(qa, answer=answer, kind='answer', filing_text=source,
        citations=[{'n': 1, 'excerpt': excerpt, 'section_ref': 'Consolidated Statements of Operations',
                    'verified': False}])
    assert result.numeric_recall == 1.0
    assert not result.passed and result.unverified_excerpts == [excerpt]
    assert result.gate_failures == ['CITATION: 1 excerpt(s) not found verbatim in filing']
