"""Create a compact Git-ready release using an explicit allowlist.

Original solver artifacts are read-only inputs. Public JSON provenance strings
are normalized; numerical arrays and the AEDT project are unchanged.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import zipfile

ROOT = Path(__file__).resolve().parent
ROOT_FILES = [
    '.gitignore','.gitattributes','README.md','NOTICE.md',
    'requirements-view.txt','requirements-verified.txt',
    'cell.py','compat.py','run_hfss.py','run_study.py','analyze.py','validate_results.py',
    'export_fields.py','build_notebook.py','build_presentation.py','build_presentation_figures.py',
    'explain_geometry.py','explain_s21_linewidth.py','package_project.py',
    'Transmon_Readout_Project.ipynb','Transmon_Readout_Presentation.html'
]


def scrub(value):
    if isinstance(value, dict):
        return {k:scrub(v) for k,v in value.items()}
    if isinstance(value, list):
        return [scrub(v) for v in value]
    if isinstance(value, str):
        normalized=value.replace('\\','/')
        prefix=ROOT.as_posix()+'/'
        if normalized.lower().startswith(prefix.lower()):
            return normalized[len(prefix):]
        if re.match(r'^[A-Za-z]:/Users/',normalized,re.I):
            return '<recorded local Python executable>'
    return value


def finalize(destination, archive):
    payload={
        'release':'transmon-readout-cell-presentation-v1',
        'numerical_results':'Original solver data preserved; only JSON provenance paths normalized',
        'solver_cache_included':False,
        'files':[]
    }
    for path in sorted(destination.rglob('*')):
        if path.is_file() and path.name!='MANIFEST.json':
            data=path.read_bytes()
            payload['files'].append({'path':path.relative_to(destination).as_posix(),
                                     'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
    (destination/'MANIFEST.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as output:
        for path in sorted(destination.rglob('*')):
            if path.is_file():
                output.write(path,arcname=destination.name+'/'+path.relative_to(destination).as_posix())
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix('.zip.sha256').write_text(f'{digest}  {archive.name}\n',encoding='utf-8')
    return payload


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--name',default='transmon-readout-cell-v1')
    args=parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*',args.name):
        raise ValueError('Use a simple release folder name without path separators')
    destination=ROOT/'dist'/args.name
    if destination.exists():
        raise FileExistsError('Release already exists; use a new --name for another release')
    destination.mkdir(parents=True)
    for name in ROOT_FILES:
        shutil.copy2(ROOT/name,destination/name)
    for subdir in ['docs','figures']:
        for source in (ROOT/subdir).glob('*'):
            if source.is_file() and source.suffix in ('.md','.png'):
                target=destination/subdir/source.name
                target.parent.mkdir(exist_ok=True)
                shutil.copy2(source,target)
    (destination/'models').mkdir()
    for name in ['readout_cell_v2.aedt','README.md']:
        shutil.copy2(ROOT/'models'/name,destination/'models'/name)
    (destination/'results').mkdir()
    for source in (ROOT/'results').iterdir():
        if not source.is_file() or source.suffix not in ('.json','.csv','.fld'):
            continue
        if source.name.startswith('status_') or source.name=='study_status.json':
            continue
        target=destination/'results'/source.name
        if source.suffix=='.json':
            original=json.loads(source.read_text(encoding='utf-8'))
            public=scrub(original)
            if 'distributed_file' in public:
                public['distributed_file_included']=False
            target.write_text(json.dumps(public,ensure_ascii=False,indent=2),encoding='utf-8')
            if source.name.startswith('epr_'):
                assert public['variations']==original['variations']
        else:
            shutil.copy2(source,target)
    # No local user path should remain in the public notebook, text or model.
    for path in destination.rglob('*'):
        if path.is_file() and path.suffix.lower() not in ('.png',):
            text=path.read_text(encoding='utf-8',errors='replace')
            assert not re.search(r'[A-Za-z]:[\\/]+Users[\\/]+',text,re.I),str(path)
    assert (destination/'models/readout_cell_v2.aedt').read_bytes()==(ROOT/'models/readout_cell_v2.aedt').read_bytes()
    archive=destination.with_suffix('.zip')
    manifest=finalize(destination,archive)
    print(json.dumps({'folder':str(destination),'zip':str(archive),
                      'files':len(manifest['files'])+1,'zip_bytes':archive.stat().st_size},indent=2))


if __name__=='__main__':
    main()
