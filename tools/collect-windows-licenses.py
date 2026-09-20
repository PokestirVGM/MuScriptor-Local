"""Bundle notices for the frontend and provide exact corresponding-source links."""
from importlib.metadata import distribution
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
import urllib.request

root = Path(__file__).resolve().parents[1]
output = Path(sys.argv[1])
output.mkdir(parents=True, exist_ok=True)
for name in ('LICENSE', 'THIRD_PARTY_NOTICES.md', 'PRIVACY.md'):
    shutil.copy2(root / name, output / name)
shutil.copytree(root / 'licenses', output / 'licenses', dirs_exist_ok=True)
python_license = Path(sys.base_prefix) / 'LICENSE.txt'
if not python_license.is_file():
    raise RuntimeError('Python runtime license is missing')
shutil.copy2(python_license, output / 'Python-LICENSE.txt')
for package in ('PySide6-Essentials', 'shiboken6', 'pyinstaller'):
    installed = distribution(package)
    destination = output / package
    destination.mkdir(exist_ok=True)
    (destination / 'PACKAGE-METADATA.txt').write_text(installed.read_text('METADATA') or '', encoding='utf-8')
    for path in installed.files or []:
        if any(word in path.name.lower() for word in ('license', 'copying', 'notice')):
            source = Path(installed.locate_file(path))
            if source.is_file():
                shutil.copy2(source, destination / path.name)
# Wheel metadata does not include all Qt/PySide notices. Copy the notices from
# the exact official source archives without extracting/executing source code.
archives = {
    'QtBase-6.8.3': 'https://download.qt.io/archive/qt/6.8/6.8.3/submodules/qtbase-everywhere-src-6.8.3.tar.xz',
    'PySide-6.8.3': 'https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.8.3-src/pyside-setup-everywhere-src-6.8.3.tar.xz',
}
with tempfile.TemporaryDirectory() as temporary:
    for name, url in archives.items():
        archive = Path(temporary) / (name + '.tar.xz')
        urllib.request.urlretrieve(url, archive)
        count = 0
        with tarfile.open(archive) as tar:
            for member in tar:
                relative = Path(*Path(member.name).parts[1:])
                if not member.isfile() or relative.is_absolute() or '..' in relative.parts:
                    continue
                lowered = str(relative).lower()
                if any(word in relative.name.lower() for word in ('license', 'copying', 'copyright', 'notice', 'qt_attribution')) or lowered.startswith('licenses/'):
                    target = output / name / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(tar.extractfile(member).read())
                    count += 1
        if not count:
            raise RuntimeError(f'No notices found for {name}')
(output / 'QT-SOURCE-AND-RELINKING.txt').write_text(
    'Qt/PySide6/Shiboken6 are used under LGPLv3. Corresponding source:\n' +
    '\n'.join(f'{name}: {url}' for name, url in archives.items()) +
    '\n\nThe app uses separately distributed Qt DLLs in its _internal directory.\n'
    'Compatible rebuilt libraries can replace them; no check prevents replacement.\n'
    'The wrapper source and build scripts are available at:\n'
    'https://github.com/PokestirVGM/MuScriptor-Local/tree/main\n', encoding='utf-8')
