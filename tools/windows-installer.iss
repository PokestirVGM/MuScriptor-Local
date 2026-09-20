[Setup]
AppId={{CA431D2A-667D-4B97-AEF5-FE2B0219C01B}
AppName=MuScriptor Local
AppVersion=1.0.0-beta
AppVerName=MuScriptor Local 1.0 Beta Preview
AppPublisher=MuScriptor Local contributors
AppPublisherURL=https://github.com/PokestirVGM/MuScriptor-Local
DefaultDirName={localappdata}\Programs\MuScriptor Local
DefaultGroupName=MuScriptor Local
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible and not arm64
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\dist\windows
OutputBaseFilename=MuScriptor-Local-Windows-x64-Setup-Preview
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\MuScriptor Local.exe
LicenseFile=..\LICENSE
CloseApplications=yes

[Files]
Source: "..\build\windows\dist\MuScriptor Local\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Icons]
Name: "{group}\MuScriptor Local"; Filename: "{app}\MuScriptor Local.exe"
Name: "{autodesktop}\MuScriptor Local"; Filename: "{app}\MuScriptor Local.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\MuScriptor Local.exe"; Description: "Open MuScriptor Local"; Flags: nowait postinstall skipifsilent

; Engine, model caches, credentials, recordings, and MIDI live outside {app}.
; Uninstall intentionally removes only the application and its shortcuts.
