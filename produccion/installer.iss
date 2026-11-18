#define MyAppVersion "1.3.0"
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
SetupIconFile=..\accessible_ai_assistant\assets\nexo.ico

[Tasks]
Name: "autostart"; Description: "Iniciar Nexo en segundo plano al iniciar sesión en Windows"

[InstallDelete]
Type: files; Name: "{userstartup}\Nexo.lnk"

[Files]
Source: "dist\Nexo\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "dist\ConfigurarClaves.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Nexo"; Filename: "{app}\Nexo.exe"
Name: "{group}\Configurar claves API"; Filename: "{app}\ConfigurarClaves.exe"
Name: "{autodesktop}\Nexo"; Filename: "{app}\Nexo.exe"
Name: "{userstartup}\Nexo"; Filename: "{app}\Nexo.exe"; Parameters: "--background"; Tasks: autostart

[Run]
Filename: "{app}\Nexo.exe"; Description: "Abrir Nexo"; Flags: nowait postinstall skipifsilent
Filename: "{app}\Nexo.exe"; Parameters: "--updated --background"; Flags: nowait runasoriginaluser; Check: AutoUpdateBackground
Filename: "{app}\Nexo.exe"; Parameters: "--updated"; Flags: nowait runasoriginaluser; Check: AutoUpdateWindow

[Code]
function AutoUpdateBackground(): Boolean;
begin
  Result := ExpandConstant('{param:NEXOAUTO|}') = 'background';
end;

function AutoUpdateWindow(): Boolean;
begin
  Result := ExpandConstant('{param:NEXOAUTO|}') = 'window';
end;

function InitializeSetup(): Boolean;
var
  Attempt: Integer;
begin
  Result := True;
  if AutoUpdateBackground() or AutoUpdateWindow() then
  begin
    for Attempt := 1 to 100 do
    begin
      if not CheckForMutexes('Local\Nexo-installed') then
        Exit;
      Sleep(100);
    end;
    Result := False;
  end;
end;
