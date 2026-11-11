"""Small real-CST infrastructure check, separate from the student's P1 task.

API source: installed CST 2025 Online Help/Python and VBA_3D.
Only creates/closes its own DesignEnvironment; never attaches to user projects.
"""
import argparse
import csv
import json
import math
import sys
import time
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--install', required=True)
    ap.add_argument('--output', required=True)
    ap.add_argument('--length-mm', type=float, default=10)
    ap.add_argument('--geometry-only', action='store_true')
    args = ap.parse_args()
    if not math.isfinite(args.length_mm) or not 1 <= args.length_mm <= 50:
        ap.error('Smoke model length must be between 1 and 50 mm.')
    sys.path.insert(0, str(Path(args.install) / 'AMD64/python_cst_libraries'))
    import cst.interface
    import cst.results

    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    project_path = out / 'waveguide.cst'
    code = f'''With Units
 .Geometry "mm"
 .Frequency "GHz"
 .Time "ns"
End With
With Background
 .Type "Normal"
 .Epsilon "1"
 .Mue "1"
 .XminSpace "0"
 .XmaxSpace "0"
 .YminSpace "0"
 .YmaxSpace "0"
 .ZminSpace "0"
 .ZmaxSpace "0"
End With
With Brick
 .Reset
 .Name "vacuum_guide"
 .Component "smoke"
 .Material "Vacuum"
 .Xrange "0", "22.86"
 .Yrange "0", "10.16"
 .Zrange "0", "{args.length_mm}"
 .Create
End With
With Boundary
 .Xmin "electric"
 .Xmax "electric"
 .Ymin "electric"
 .Ymax "electric"
 .Zmin "electric"
 .Zmax "electric"
End With
Solver.FrequencyRange "8", "12"
'''
    for number, face in [(1, 'zmin'), (2, 'zmax')]:
        code += f'''With Port
 .Reset
 .PortNumber "{number}"
 .NumberOfModes "1"
 .Coordinates "Full"
 .Orientation "{face}"
 .PortOnBound "True"
 .Create
End With
'''
    code += '''ChangeSolverType "HF Time Domain"
With Solver
 .Method "Hexahedral"
 .CalculationType "TD-S"
 .StimulationPort "1"
 .StimulationMode "1"
 .SteadyStateLimit "-40"
End With
'''
    (out / 'history.vba').write_text(code, encoding='utf-8')
    de = None
    prj = None
    begin = time.monotonic()
    result = {'source': 'cst', 'length_mm': args.length_mm, 'status': 'running'}
    try:
        print('Starting an isolated CST instance', flush=True)
        de = cst.interface.DesignEnvironment.new()
        de.set_quiet_mode(True)
        prj = de.new_mws()
        prj.model3d.add_to_history('Infrastructure smoke: straight guide', code, timeout=60)
        prj.save(str(project_path), include_results=True)
        result['geometry_saved'] = project_path.exists()
        result['solver'] = prj.model3d.get_active_solver_name()
        print('Geometry and ports saved', flush=True)
        if args.geometry_only:
            result['status'] = 'passed' if result['geometry_saved'] else 'failed'
        else:
            print('Running CPU-default time-domain solver', flush=True)
            try:
                prj.model3d.run_solver(timeout=180)
            except Exception:
                if prj.model3d.is_solver_running(timeout=10):
                    prj.model3d.abort_solver(timeout=15)
                raise
            prj.save(include_results=True)
            prj.close()
            prj = None
            data = cst.results.ProjectFile(str(project_path), allow_interactive=False).get_3d()
            tree = data.get_tree_items()
            (out / 'result-tree.json').write_text(json.dumps(tree, ensure_ascii=False, indent=2), encoding='utf-8')
            s11 = data.get_result_item(r'1D Results\S-Parameters\S1,1')
            s21 = data.get_result_item(r'1D Results\S-Parameters\S2,1')
            frequencies = s11.get_xdata()
            if list(frequencies) != list(s21.get_xdata()):
                raise ValueError('S11/S21 frequency grids differ')
            rows = []
            for f, r, t in zip(frequencies, s11.get_ydata(), s21.get_ydata()):
                rows.append([f, r.real, r.imag, t.real, t.imag, abs(r)**2, abs(t)**2])
            if not rows or not all(math.isfinite(v) for row in rows for v in row):
                raise ValueError('Missing/nonfinite solver results')
            with (out / 'sparameters.csv').open('w', encoding='utf-8', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(['frequency_GHz', 's11_real', 's11_imag', 's21_real', 's21_imag', 'R', 'T'])
                writer.writerows(rows)
            result['samples'] = len(rows)
            result['max_reflection_power'] = max(row[5] for row in rows)
            result['max_power_balance_error'] = max(abs(row[5]+row[6]-1) for row in rows)
            middle = min(rows, key=lambda row: abs(row[0]-10))
            result['s21_phase_10GHz_rad'] = math.atan2(middle[4], middle[3])
            result['criteria'] = {'max_reflection_power': 0.01, 'max_power_balance_error': 0.02}
            result['status'] = 'passed' if result['max_reflection_power'] < 0.01 and result['max_power_balance_error'] < 0.02 else 'failed'
            print('Exported and checked S-parameters', flush=True)
    except Exception as exc:
        result.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        print(result['error'], flush=True)
    finally:
        if prj is not None:
            prj.close()
        if de is not None:
            de.close()
        result['elapsed_s'] = round(time.monotonic()-begin, 3)
        (out / 'worker-result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
