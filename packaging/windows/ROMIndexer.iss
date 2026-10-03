#define AppName "ROM Indexer"
#define AppVersion "0.1.0"
#define AppPublisher "ROM Indexer"

[Setup]
AppId={{A9D9CB6D-01E7-4A53-A8BE-C67B498C2457}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\ROM Indexer
DefaultGroupName={#AppName}
UninstallDisplayIcon={app}\ROMIndexer.exe
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\..\dist\installer
OutputBaseFilename=ROMIndexer-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
DisableProgramGroupPage=yes

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "..\..\dist\ROMIndexer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\ROM Indexer"; Filename: "{app}\ROMIndexer.exe"
Name: "{autodesktop}\ROM Indexer"; Filename: "{app}\ROMIndexer.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\ROMIndexer.exe"; Description: "Launch ROM Indexer"; Flags: nowait postinstall skipifsilent