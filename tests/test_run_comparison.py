"""Offline orchestration checks; subprocesses and waits are mocked."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


spec = importlib.util.spec_from_file_location('run_comparison', Path(__file__).resolve().parents[1]/'scripts/run_comparison.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
TRIAL = '10-fish__0066'


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def ready_inputs(data):
    data.mkdir(parents=True, exist_ok=True)
    files = {}
    for name in runner.INPUT_MEMBERS:
        (data/name).write_bytes(name.encode())
        files[name] = {'sha256': runner.file_hash(data/name), 'size': (data/name).stat().st_size}
    write_json(data/'provenance.json', {'files': files})


def completed(tmp_path):
    repo = tmp_path/'repo'
    config = repo/'config.json'
    write_json(config, {'trials': [TRIAL]})
    data = repo/'data'/TRIAL
    ready_inputs(data)
    output = repo/'out'/TRIAL
    write_json(output/'summary.json', {'trial': '10-fish/0066', 'network': {'network_rows': 1}})
    source_paths = [config]
    for name in ['compare_trial.py', 'metrics.py', 'network_summary.py']:
        path = repo/'src/shiners'/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(name)
        source_paths.append(path)
    provenance = {
        'input_hashes': {str(data/name): runner.file_hash(data/name)
                         for name in (*runner.INPUT_MEMBERS, 'provenance.json')},
        'source_hashes': {str(p.relative_to(repo)): runner.file_hash(p) for p in source_paths},
        'output_hashes': {'summary.json': runner.file_hash(output/'summary.json')},
        'fetch_member_hashes_match': True,
    }
    write_json(output/'provenance.json', provenance)
    return repo, config, data, output, provenance


def test_fresh_processes_follow_config_order_and_selection(tmp_path, monkeypatch):
    config = tmp_path/'config.json'
    trials = [TRIAL, '30-fish__0084']
    write_json(config, {'trials': trials})
    for trial in trials:
        ready_inputs(tmp_path/'data'/trial)
    calls = []
    monkeypatch.setattr(runner.subprocess, 'run', lambda args, **kw: calls.append((args, kw)))
    runner.run(config, tmp_path/'data', tmp_path/'out')
    assert len(calls) == 2
    for (args, kw), trial in zip(calls, trials):
        assert args == [sys.executable, '-m', 'shiners.compare_trial', '--data', str(tmp_path/'data'/trial),
                        '--output', str(tmp_path/'out'/trial), '--config', str(config)]
        assert kw == {'cwd': runner.ROOT, 'check': True}
    calls.clear()
    runner.run(config, tmp_path/'data', tmp_path/'out', trials=[trials[1], trials[1]])
    assert len(calls) == 1
    assert calls[0][0][4].endswith(trials[1])


def test_waits_until_ready_announces_only_once(tmp_path, monkeypatch, capsys):
    config = tmp_path/'config.json'
    write_json(config, {'trials': [TRIAL]})
    readiness = iter([False, False, True])
    sleeps, calls = [], []
    monkeypatch.setattr(runner, 'downloads_ready', lambda _: next(readiness))
    monkeypatch.setattr(runner.time, 'sleep', sleeps.append)
    monkeypatch.setattr(runner.subprocess, 'run', lambda *args, **kw: calls.append(args))
    runner.run(config, tmp_path/'data', tmp_path/'out', wait_for_downloads=True)
    assert sleeps == [10, 10]
    assert len(calls) == 1
    assert capsys.readouterr().out.count('waiting for') == 1


def test_ready_requires_both_members_and_completed_entries(tmp_path):
    data = tmp_path/TRIAL
    assert not runner.downloads_ready(data)
    ready_inputs(data)
    assert runner.downloads_ready(data)
    provenance = json.loads((data/'provenance.json').read_text())
    provenance['files'].pop('networks.parquet')
    write_json(data/'provenance.json', provenance)
    assert not runner.downloads_ready(data)
    ready_inputs(data)
    (data/'networks.parquet').write_bytes(b'short')
    assert not runner.downloads_ready(data)


def test_resume_checks_all_manifests_then_skips(tmp_path, monkeypatch, capsys):
    repo, config, data, output, _ = completed(tmp_path)
    validate = runner.validate_completed
    hashed = []
    actual_hash = runner.file_hash
    monkeypatch.setattr(runner, 'file_hash', lambda path: hashed.append(path) or actual_hash(path))
    monkeypatch.setattr(runner, 'validate_completed', lambda o, d, c: validate(o, d, c, repo))
    monkeypatch.setattr(runner.subprocess, 'run', lambda *a, **k: pytest.fail('Completed trial must not run'))
    runner.run(config, data.parent, output.parent, resume=True)
    assert len(hashed) == 8  # Three inputs, four sources, one output.
    assert 'verified complete; skipping' in capsys.readouterr().out


@pytest.mark.parametrize('category', ['input_hashes', 'source_hashes', 'output_hashes'])
def test_resume_rejects_each_kind_of_changed_file(tmp_path, category):
    repo, config, data, output, provenance = completed(tmp_path)
    name = next(iter(provenance[category]))
    root = output if category == 'output_hashes' else repo
    path = runner._resolve_recorded(name, root)
    path.write_bytes(path.read_bytes()+b'changed')
    with pytest.raises(ValueError, match=category):
        runner.validate_completed(output, data, config, repo)


def test_resume_rejects_partial_or_untracked_outputs_without_changes(tmp_path):
    repo, config, data, output, _ = completed(tmp_path)
    extra = output/'unexpected.csv'
    extra.write_text('partial')
    with pytest.raises(ValueError, match='unrecorded'):
        runner.validate_completed(output, data, config, repo)
    assert extra.read_text() == 'partial'
    (output/'summary.json').unlink()
    with pytest.raises(ValueError, match='Partial output'):
        runner.validate_completed(output, data, config, repo)


def test_nonempty_output_requires_resume_and_missing_downloads_fail(tmp_path, monkeypatch):
    _, config, data, output, _ = completed(tmp_path)
    monkeypatch.setattr(runner.subprocess, 'run', lambda *a, **k: pytest.fail('Must not run'))
    with pytest.raises(ValueError, match='Nonempty output'):
        runner.run(config, data.parent, output.parent)
    with pytest.raises(ValueError, match='incomplete'):
        runner.run(config, tmp_path/'missing', tmp_path/'fresh')
    with pytest.raises(ValueError, match='--trial'):
        runner.run(config, data.parent, output.parent, trials=['70-fish__0103'])


def test_child_failure_stops_later_trials(tmp_path, monkeypatch):
    config = tmp_path/'config.json'
    write_json(config, {'trials': [TRIAL, '30-fish__0084']})
    ready_inputs(tmp_path/'data'/TRIAL)
    calls = []
    def fail(args, **kwargs):
        calls.append(args)
        raise subprocess.CalledProcessError(1, args)
    monkeypatch.setattr(runner.subprocess, 'run', fail)
    with pytest.raises(subprocess.CalledProcessError):
        runner.run(config, tmp_path/'data', tmp_path/'out')
    assert len(calls) == 1
