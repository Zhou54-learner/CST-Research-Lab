"""Focused acceptance checks: real solver evidence and optional local browser QA."""
import argparse
import cmath
import csv
import json
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import lab


def verify_records():
    lab.check()
    records = lab.runs()
    cst = [r for r in records if r['source'] == 'cst' and r['status'] == 'passed']
    if not {10.0, 12.0}.issubset({r['task']['parameters']['length_mm'] for r in cst}):
        raise AssertionError('Acceptance requires real CST runs at both 10 and 12 mm')
    comparisons = []
    for run in cst:
        length = run['task']['parameters']['length_mm'] / 1000
        with (lab.ROOT/'runs'/run['run_id']/'sparameters.csv').open(encoding='utf-8') as file:
            rows = list(csv.DictReader(file))
        errors = []
        powers = []
        for r in rows:
            f = float(r['frequency_GHz'])*1e9
            beta = math.sqrt((2*math.pi*f/299792458.0)**2-(math.pi/0.02286)**2)
            expected = cmath.exp(-1j*beta*length)
            measured = complex(float(r['s21_real']), float(r['s21_imag']))
            reflected = complex(float(r['s11_real']), float(r['s11_imag']))
            errors.append(abs(measured-expected))
            powers.append(abs(abs(measured)**2+abs(reflected)**2-1))
        if max(errors) >= 0.02:
            raise AssertionError(f'{run["run_id"]}: complex S21 disagrees with ideal propagation')
        if abs(max(powers)-run['metrics']['max_power_balance_error']) > 1e-12:
            raise AssertionError('Reported metrics differ from raw complex data')
        comparisons.append({'run_id':run['run_id'], 'length_mm':length*1000, 'max_complex_s21_error':max(errors), 'limit':0.02})
    # Invalid task must fail before a run or solver is started.
    before = len(lab.runs())
    for invalid in ['-1', 'nan']:
        proc = subprocess.run([sys.executable, str(lab.ROOT/'tools/lab.py'), 'smoke', '--length-mm', invalid], capture_output=True)
        if proc.returncode == 0 or len(lab.runs()) != before:
            raise AssertionError('Invalid input was accepted or created a run')
    # A stale page must be detected. Isolated fixture avoids touching user state.
    original_root, original_state = lab.ROOT, lab.STATE
    try:
        with tempfile.TemporaryDirectory() as folder:
            lab.ROOT = Path(folder)
            lab.STATE = lab.ROOT/'learning-state.json'
            lab.write(lab.STATE, lab.read(original_state))
            (lab.ROOT/'ui').mkdir()
            (lab.ROOT/'ui/dashboard.html').write_text('__LAB_DATA__', encoding='utf-8')
            lab.refresh()
            lab.check()
            (lab.ROOT/'index.html').write_text('stale', encoding='utf-8')
            try:
                lab.check()
            except ValueError as error:
                if 'stale' not in str(error):
                    raise
            else:
                raise AssertionError('Stale page was not detected')
            # A missing local CST configuration becomes an explicit failed run.
            # No application is started in this isolated fixture.
            (lab.ROOT/'tools').mkdir()
            for name in ['lab.py', 'cst_worker.py']:
                shutil.copy2(original_root/'tools'/name, lab.ROOT/'tools'/name)
            if lab.smoke('cst', 10) != 1:
                raise AssertionError('Missing CST configuration did not fail')
            failed = lab.runs()
            if len(failed) != 1 or failed[0]['status'] != 'failed' or not failed[0].get('error'):
                raise AssertionError('Failed task was not recorded')
            lab.check()
    finally:
        lab.ROOT, lab.STATE = original_root, original_state
    return {'solver_vs_analytic':comparisons, 'invalid_input_rejected':True, 'stale_page_detected':True, 'failed_run_recorded':True, 'artifact_hashes_verified':True}


def verify_browser():
    from playwright.sync_api import sync_playwright
    errors = []
    network = []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='chrome', headless=True)
        page = browser.new_page(viewport={'width':1440,'height':1080}, device_scale_factor=1)
        page.on('pageerror', lambda err: errors.append(str(err)))
        page.on('request', lambda req: network.append(req.url) if req.url.startswith(('http:', 'https:')) else None)
        page.goto((lab.ROOT/'index.html').as_uri())
        assert page.locator('[data-project]').count() == 11
        page.locator('[data-project="P8"]').click()
        assert '自适应采样' in page.locator('#project-detail').inner_text()
        page.locator('.skill summary').first.click()
        assert page.locator('.skill').first.get_attribute('open') is not None
        page.screenshot(path=str(lab.ROOT/'.local/dashboard-desktop.png'), full_page=True)
        page.get_by_role('tab', name='运行与证据').click()
        assert page.locator('#runs tr').count() == len(lab.runs())
        page.locator('#comparison summary').click()
        page.locator('#quantity').select_option('phase')
        assert page.locator('#chart polyline').count() == 2
        page.screenshot(path=str(lab.ROOT/'.local/dashboard-evidence.png'), full_page=True)
        page.get_by_role('tab', name='学习记忆').click()
        assert page.locator('.memory-card').count() == len(lab.read(lab.STATE)['memory'])
        page.get_by_role('tab', name='学习记忆').press('Home')
        assert page.get_by_role('tab', name='学习路径').get_attribute('aria-selected') == 'true'
        # Every local link points to an existing artifact or document.
        broken = []
        for href in page.locator('a[href]').evaluate_all('(els)=>els.map(e=>e.getAttribute("href"))'):
            if href.startswith(('http:', 'https:', '#')):
                continue
            if not (lab.ROOT/href).is_file():
                broken.append(href)
        assert not broken, f'Broken local links: {broken}'
        page.set_viewport_size({'width':390,'height':844})
        page.screenshot(path=str(lab.ROOT/'.local/dashboard-mobile.png'), full_page=True)
        for name in ['学习路径','运行与证据','学习记忆']:
            page.get_by_role('tab', name=name).click()
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), f'Mobile overflow: {name}'
        assert not errors, errors
        assert not network, network
        browser.close()
    return {'browser':'Chrome headless', 'desktop':'1440×1080', 'mobile':'390×844', 'tabs_and_keyboard':True, 'project_details':True, 'comparison_chart':True, 'local_links':True, 'javascript_errors':errors, 'external_requests':network}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--browser', action='store_true', help='Requires optional Playwright and installed Chrome')
    args = parser.parse_args()
    result = {'checked_at':lab.stamp(), 'verification_script_sha256':lab.digest(__file__), 'functional':verify_records()}
    if args.browser:
        result['browser'] = verify_browser()
    lab.write(lab.ROOT/'docs/acceptance.json', result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
