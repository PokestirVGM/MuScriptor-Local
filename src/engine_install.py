"""Staged engine refresh with rollback after copy failures or interruption."""
import json
import os
from pathlib import Path
import shutil
import sys

ITEMS = ('src/worker.py', 'upstream/muscriptor')


def remove(path):
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def recover(root):
    transaction = root / '.engine-update'
    journal = transaction / 'journal.json'
    if journal.exists():
        existed = json.loads(journal.read_text())
        for i, item in enumerate(ITEMS):
            target, backup = root / item, transaction / f'backup-{i}'
            if backup.exists():
                remove(target)
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(backup, target)
            elif not existed[i]:
                remove(target)
    remove(transaction)


def install(root, bundled_worker, bundled_package):
    root = Path(root)
    recover(root)
    transaction = root / '.engine-update'
    transaction.mkdir()
    try:
        shutil.copy2(bundled_worker, transaction / 'new-0')
        shutil.copytree(bundled_package, transaction / 'new-1', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        if not (transaction / 'new-1/transcription_model.py').is_file():
            raise OSError('Bundled engine is incomplete')
        existed = [(root / item).exists() for item in ITEMS]
        (transaction / 'journal.json').write_text(json.dumps(existed))
        for i, item in enumerate(ITEMS):
            target = root / item
            target.parent.mkdir(parents=True, exist_ok=True)
            if existed[i]:
                os.replace(target, transaction / f'backup-{i}')
            os.replace(transaction / f'new-{i}', target)
        # Removing the journal commits both replacements. Backups are then
        # disposable; an interrupted cleanup never rolls back a committed update.
        (transaction / 'journal.json').unlink()
    except BaseException:
        recover(root)
        raise
    remove(transaction)


if __name__ == '__main__':
    install(*sys.argv[1:])
