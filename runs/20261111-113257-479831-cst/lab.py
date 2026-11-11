"""Minimal lab CLI. Python standard library only; CST is loaded by its worker."""
import argparse
import csv
import hashlib
import html
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / 'learning-state.json'


def stamp():
    return datetime.now().astimezone().isoformat(timespec='seconds')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    tmp.replace(path)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def relative(path):
    return Path(path).resolve().relative_to(ROOT.resolve()).as_posix()


def runs():
    return [read(p) for p in sorted((ROOT / 'runs').glob('*/run.json'))]


def payload():
    records = runs()
    for run in records:
        table = ROOT / 'runs' / run['run_id'] / 'sparameters.csv'
        if table.exists():
            with table.open(encoding='utf-8') as file:
                rows = list(csv.DictReader(file))
            step = max(1, (len(rows)-1)//100)
            sampled = rows[::step]
            if rows and sampled[-1] is not rows[-1]:
                sampled.append(rows[-1])
            run['curve'] = [{'f': float(r['frequency_GHz']), 'R': float(r['R']), 'T': float(r['T']), 'phase': math.atan2(float(r['s21_imag']), float(r['s21_real']))} for r in sampled]
    return {'state': read(STATE), 'runs': records, 'environment': read(ROOT / 'docs/environment.json') if (ROOT / 'docs/environment.json').exists() else None}


def refresh():
    data = json.dumps(payload(), ensure_ascii=False, allow_nan=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    template = (ROOT / 'ui/dashboard.html').read_text(encoding='utf-8')
    if template.count('__LAB_DATA__') != 1:
        raise ValueError('Dashboard requires exactly one data placeholder')
    (ROOT / 'index.html').write_text(template.replace('__LAB_DATA__', data), encoding='utf-8')
    print('Updated index.html')


def doctor(install):
    install = Path(install).resolve()
    report = {'checked_at': stamp(), 'python': platform.python_version(), 'platform': platform.system(), 'cst_version': '2025', 'checks': {}}
    report['checks']['cst_executable'] = (install / 'CST DESIGN ENVIRONMENT.exe').exists()
    report['checks']['python_interface'] = False
    report['checks']['result_reader'] = False
    try:
        sys.path.insert(0, str(install / 'AMD64/python_cst_libraries'))
        import cst.interface
        report['checks']['python_interface'] = True
        import cst.results
        report['checks']['result_reader'] = True
    except Exception as exc:
        report['import_error'] = f'{type(exc).__name__}: {exc}'
    if platform.system() == 'Windows':
        command = "[pscustomobject]@{cpu=(Get-CimInstance Win32_Processor).Name;ram_gb=[math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB,1);gpu=@((Get-CimInstance Win32_VideoController).Name)} | ConvertTo-Json -Compress"
        probe = subprocess.run(['powershell', '-NoProfile', '-Command', command], capture_output=True, text=True, timeout=30)
        if probe.returncode == 0:
            report['hardware'] = json.loads(probe.stdout)
    report['tools'] = {}
    for name, args in [('git', ['--version']), ('node', ['--version'])]:
        if shutil.which(name):
            report['tools'][name] = subprocess.run([name, *args], capture_output=True, text=True, timeout=10).stdout.strip()
    report['solver_validation'] = 'See actual CST run records; imports alone do not establish solver availability.'
    report['not_tested'] = ['thermal solver', 'GPU acceleration', 'frequency-domain solver', 'MCP server', 'autonomous research agent']
    write(ROOT / '.local/config.json', {'cst_install': str(install)})
    write(ROOT / 'docs/environment.json', report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if STATE.exists() and (ROOT / 'ui/dashboard.html').exists():
        refresh()
    return 0 if all(report['checks'].values()) else 1


def analytic(out, length):
    # Ideal lossless TE10 propagation: reference fixture for the smoke model.
    c = 299792458.0
    a = 22.86e-3
    rows = []
    for i in range(101):
        f = 8 + 4*i/100
        beta = math.sqrt((2*math.pi*f*1e9/c)**2-(math.pi/a)**2)
        phase = -beta*length/1000
        rows.append([f, 0, 0, math.cos(phase), math.sin(phase), 0, 1])
    with (out/'sparameters.csv').open('w', encoding='utf-8', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['frequency_GHz', 's11_real', 's11_imag', 's21_real', 's21_imag', 'R', 'T'])
        writer.writerows(rows)
    return {'status': 'passed', 'source': 'analytic', 'samples': len(rows), 'max_reflection_power': 0.0, 'max_power_balance_error': 0.0, 's21_phase_10GHz_rad': math.atan2(rows[50][4], rows[50][3])}


def plot(out, source):
    with (out/'sparameters.csv').open(encoding='utf-8') as file:
        rows = list(csv.DictReader(file))
    series = ''
    for key, color in [('R', '#a65b2d'), ('T', '#12685e')]:
        pts = ' '.join(f'{60+(float(r["frequency_GHz"])-8)/4*600:.2f},{220-float(r[key])*180:.2f}' for r in rows)
        series += f'<polyline fill="none" stroke="{color}" stroke-width="2.2" points="{pts}"/>'
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 280" role="img" aria-label="Power reflection and transmission">
<rect width="720" height="280" fill="#fbfaf6"/><g font-family="sans-serif" font-size="13" fill="#30413c">
<text x="60" y="22">{html.escape(source)} · WR90 smoke · R / T</text>
<path d="M60 40V220H660" fill="none" stroke="#82928c"/>
<text x="35" y="46">1</text><text x="35" y="224">0</text>
<text x="60" y="245">8</text><text x="350" y="245">10</text><text x="640" y="245">12 GHz</text>
<text x="500" y="22" fill="#a65b2d">R</text><text x="550" y="22" fill="#12685e">T</text>{series}</g></svg>'''
    (out/'power.svg').write_text(svg, encoding='utf-8')


def smoke(backend, length):
    if not math.isfinite(length) or not 1 <= length <= 50:
        raise ValueError('Infrastructure guide length must be finite and within 1–50 mm')
    run_id = datetime.now().astimezone().strftime('%Y%m%d-%H%M%S-%f')+'-'+backend
    out = ROOT/'runs'/run_id
    out.mkdir(parents=True)
    record = {'schema_version': 1, 'run_id': run_id, 'project_id': 'INFRA', 'status': 'running', 'source': backend, 'started_at': stamp(),
              'task': {'goal': 'Verify tool → data → checks → dashboard; not a student project', 'parameters': {'length_mm': length, 'width_mm': 22.86, 'height_mm': 10.16, 'frequency_GHz': [8, 12]}, 'budget': {'solver_timeout_s': 180}, 'criteria': {'max_reflection_power': 0.01, 'max_power_balance_error': 0.02}},
              'implementation': {'python': platform.python_version(), 'lab_sha256': digest(__file__), 'worker_sha256': digest(ROOT/'tools/cst_worker.py')}, 'artifacts': [], 'human_interventions': None}
    for name in ['lab.py', 'cst_worker.py']:
        shutil.copy2(ROOT/'tools'/name, out/name)
    write(out/'run.json', record)
    start = time.monotonic()
    try:
        if backend == 'analytic':
            result = analytic(out, length)
        else:
            config = read(ROOT/'.local/config.json')
            record['implementation']['cst_version'] = '2025'
            # CST writes outside OneDrive; only closed outputs are archived.
            work = Path(tempfile.gettempdir())/'CST-Research-Lab'/run_id
            work.mkdir(parents=True)
            cmd = [sys.executable, str(ROOT/'tools/cst_worker.py'), '--install', config['cst_install'], '--output', str(work), '--length-mm', str(length)]
            proc = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=300, env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
            (out/'execution.log').write_text(proc.stdout+'\n'+proc.stderr, encoding='utf-8')
            result = read(work/'worker-result.json') if (work/'worker-result.json').exists() else {'status': 'failed', 'error': f'CST worker exited {proc.returncode} without result'}
            for name in ['waveguide.cst', 'history.vba', 'worker-result.json', 'result-tree.json', 'sparameters.csv', 'solver.log']:
                if (work/name).exists():
                    shutil.copy2(work/name, out/name)
            if proc.returncode != 0:
                result['status'] = 'failed'
                result.setdefault('error', f'CST worker exit code {proc.returncode}; see execution.log')
        record['status'] = result['status']
        record['metrics'] = {k: result[k] for k in ['samples', 'max_reflection_power', 'max_power_balance_error', 's21_phase_10GHz_rad'] if k in result}
        if result.get('error'):
            record['error'] = result['error']
        if (out/'sparameters.csv').exists():
            plot(out, backend)
    except Exception as exc:
        record.update(status='failed', error=f'{type(exc).__name__}: {exc}')
    record['finished_at'] = stamp()
    record['elapsed_s'] = round(time.monotonic()-start, 3)
    record['artifacts'] = [{'path': relative(p), 'sha256': digest(p)} for p in sorted(out.iterdir()) if p.is_file() and p.name != 'run.json']
    write(out/'run.json', record)
    refresh()
    print(json.dumps({'run_id': run_id, 'status': record['status'], 'metrics': record.get('metrics'), 'error': record.get('error')}, ensure_ascii=False))
    return 0 if record['status'] == 'passed' else 1


def check():
    state = read(STATE)
    expected = {'P1','P2','P3','P4','P5','P6','P7','P8','P9','T1','T2'}
    if {p['id'] for p in state['projects']} != expected:
        raise ValueError('Roadmap project set is incomplete')
    if any(p['status'] not in ['待开始', '探索中', '已完成', '待回访'] for p in state['projects']):
        raise ValueError('Invalid project status')
    for run in runs():
        if run['status'] not in ['passed', 'failed']:
            raise ValueError(f"Unfinished run: {run['run_id']}")
        for artifact in run['artifacts']:
            path = (ROOT/artifact['path']).resolve()
            if not path.is_relative_to(ROOT.resolve()) or not path.is_file() or digest(path) != artifact['sha256']:
                raise ValueError(f"Missing/changed artifact: {artifact['path']}")
        if run['status'] == 'passed' and not any(a['path'].endswith('sparameters.csv') for a in run['artifacts']):
            raise ValueError('Passed run without raw numerical data')
    template = (ROOT/'ui/dashboard.html').read_text(encoding='utf-8')
    data = json.dumps(payload(), ensure_ascii=False, allow_nan=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    if (ROOT/'index.html').read_text(encoding='utf-8') != template.replace('__LAB_DATA__', data):
        raise ValueError('Dashboard is stale; run refresh')
    print(f'PASS: {len(state["projects"])} roadmap nodes; {len(runs())} run records; artifact hashes; dashboard data consistency')
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='command', required=True)
    d = sub.add_parser('doctor'); d.add_argument('--cst-install', required=True)
    s = sub.add_parser('smoke'); s.add_argument('--backend', choices=['analytic', 'cst'], default='analytic'); s.add_argument('--length-mm', type=float, default=10)
    sub.add_parser('refresh'); sub.add_parser('check')
    args = ap.parse_args()
    try:
        if args.command == 'doctor': return doctor(args.cst_install)
        if args.command == 'smoke': return smoke(args.backend, args.length_mm)
        if args.command == 'refresh': refresh(); return 0
        return check()
    except Exception as exc:
        print(f'{type(exc).__name__}: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
