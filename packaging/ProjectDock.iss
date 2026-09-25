#ifndef AppVersion
  #error AppVersion is required
#endif
[Setup]
AppId={{D0C70C9F-7882-49D3-83F3-929EA0645173}
AppName=ProjectDock
AppVersion={#AppVersion}
AppPublisher=CctrGy
AppPublisherURL=https://github.com/CctrGy/ProjectDock
AppSupportURL=https://github.com/CctrGy/ProjectDock/issues
DefaultDirName={localappdata}\Programs\ProjectDock
DefaultGroupName=ProjectDock
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
DisableDirPage=no
DisableProgramGroupPage=yes
AllowNoIcons=yes
OutputDir=..\dist\release
OutputBaseFilename=ProjectDock-{#AppVersion}-windows-x64-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ChangesEnvironment=yes
CloseApplications=yes
RestartApplications=no
UninstallDisplayIcon={app}\ProjectDock.exe
SetupLogging=yes
[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"
[Tasks]
Name: "addtopath"; Description: "Permitir projectdock desde la terminal (PATH del usuario)"
[Files]
Source: "..\dist\ProjectDock\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{autoprograms}\ProjectDock"; Filename: "{app}\ProjectDock.exe"; Parameters: "--gui"; WorkingDir: "{app}"
Name: "{autoprograms}\ProjectDock - Desinstalar"; Filename: "{uninstallexe}"
[Run]
Filename: "{app}\ProjectDock.exe"; Parameters: "--gui"; Description: "Abrir ProjectDock"; Flags: nowait postinstall skipifsilent
[Code]
const
  SettingsKey = 'Software\ProjectDock\Installer';
function HasEntry(PathValue, Entry: String): Boolean;
var Part: String; P: Integer;
begin
  Result := False;
  while PathValue <> '' do begin
    P := Pos(';', PathValue);
    if P = 0 then P := Length(PathValue) + 1;
    Part := Trim(Copy(PathValue, 1, P - 1));
    Delete(PathValue, 1, P);
    if CompareText(RemoveBackslashUnlessRoot(Part), RemoveBackslashUnlessRoot(Entry)) = 0 then begin
      Result := True;
      Exit;
    end;
  end;
end;
procedure RemoveOwnedPath;
var OldPath, Entry, NewPath, Part: String; P: Integer;
begin
  if not RegQueryStringValue(HKCU, SettingsKey, 'AddedPath', Entry) then Exit;
  if RegQueryStringValue(HKCU, 'Environment', 'Path', OldPath) then begin
    NewPath := '';
    while OldPath <> '' do begin
      P := Pos(';', OldPath);
      if P = 0 then P := Length(OldPath) + 1;
      Part := Copy(OldPath, 1, P - 1);
      Delete(OldPath, 1, P);
      if CompareText(RemoveBackslashUnlessRoot(Trim(Part)), RemoveBackslashUnlessRoot(Entry)) <> 0 then begin
        if NewPath <> '' then NewPath := NewPath + ';';
        NewPath := NewPath + Part;
      end;
    end;
    RegWriteExpandStringValue(HKCU, 'Environment', 'Path', NewPath);
  end;
  RegDeleteValue(HKCU, SettingsKey, 'AddedPath');
end;
procedure CurStepChanged(CurStep: TSetupStep);
var OldPath, Entry, Previous: String;
begin
  if CurStep = ssPostInstall then begin
    Entry := ExpandConstant('{app}');
    if RegQueryStringValue(HKCU, SettingsKey, 'AddedPath', Previous) then
      if CompareText(Previous, Entry) <> 0 then RemoveOwnedPath;
    if WizardIsTaskSelected('addtopath') then begin
      RegQueryStringValue(HKCU, 'Environment', 'Path', OldPath);
      if not HasEntry(OldPath, Entry) then begin
        if (OldPath <> '') and (Copy(OldPath, Length(OldPath), 1) <> ';') then OldPath := OldPath + ';';
        if not RegWriteExpandStringValue(HKCU, 'Environment', 'Path', OldPath + Entry) then
          RaiseException('No se pudo actualizar el PATH del usuario.');
        RegWriteStringValue(HKCU, SettingsKey, 'AddedPath', Entry);
      end;
    end;
  end;
end;
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then RemoveOwnedPath;
end;
