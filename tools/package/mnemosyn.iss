[Setup]
AppId={{6B0C5E2A-3D4F-4E8B-9A71-2F5C8D9E1B30}
AppName=Mnemosyn
AppVersion={#AppVersion}
AppPublisher=Mnemosyn
AppPublisherURL=https://mnemo.saeed.cool/
DefaultDirName={localappdata}\Programs\Mnemosyn
DefaultGroupName=Mnemosyn
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir={#OutputDir}
OutputBaseFilename={#OutputName}
SetupIconFile={#IconFile}
UninstallDisplayIcon={app}\Mnemosyn.exe
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
LicenseFile=..\..\LICENSE

[InstallDelete]
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\Mnemosyn"; Filename: "{app}\Mnemosyn.exe"
Name: "{group}\Uninstall Mnemosyn"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\Mnemosyn.exe"; Description: "Open Mnemosyn"; Flags: nowait postinstall skipifsilent
