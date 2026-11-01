# client/packaging/albion_aware.iss
#define MyAppName "AlbionAware"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "portaler.pages.dev"

[Setup]
AppId={{8F2B7C9E-2D4A-4C3B-9E7F-1A6C5D8B0E21}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
PrivilegesRequired=admin
OutputDir=..\dist
OutputBaseFilename=AlbionAware-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
Languages: english,chinesesimplified
LicenseFile=LICENSES\AlbionAware-MIT.txt

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\AlbionAware.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\data\items.min.json"; DestDir: "{app}\data"; Flags: ignoreversion
Source: "..\OpenRadar\*"; DestDir: "{app}\OpenRadar"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "LICENSES\*"; DestDir: "{app}\LICENSES"; Flags: ignoreversion
Source: "NOTICE.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "README.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "launcher.bat"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\AlbionAware.exe"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\AlbionAware.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\AlbionAware.exe"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
