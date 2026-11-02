#define MyAppVersion "1.0.0"
[Setup]
AppId={{02A82DB4-F6FC-4859-A41F-4C15B21714AE}
AppName=Nexo
AppVersion={#MyAppVersion}
DefaultDirName={localappdata}\Programs\Nexo
DefaultGroupName=Nexo
OutputDir=.
OutputBaseFilename=Nexo-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
CloseApplications=yes
RestartApplications=no
UninstallDisplayIcon={app}\Nexo.exe

[Files]
Source: "dist\Nexo\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "dist\ConfigurarClaves.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Nexo"; Filename: "{app}\Nexo.exe"
Name: "{group}\Configurar claves API"; Filename: "{app}\ConfigurarClaves.exe"
Name: "{autodesktop}\Nexo"; Filename: "{app}\Nexo.exe"

[Run]
Filename: "{app}\Nexo.exe"; Description: "Abrir Nexo"; Flags: nowait postinstall skipifsilent
