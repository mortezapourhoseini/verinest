; Inno Setup script for VeriNest (per-user install, no administrator rights needed)
; build:  iscc /DAppVersion=1.2.0 packaging\windows\installer.iss

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6F4A1C2E-9B7D-4E1A-8C5F-2D3B9E0A7F41}
AppName=VeriNest
AppVersion={#AppVersion}
AppVerName=VeriNest {#AppVersion}
AppPublisher=VeriNest contributors
AppPublisherURL=https://github.com/mortezapourhoseini/verinest
AppSupportURL=https://github.com/mortezapourhoseini/verinest/issues
DefaultDirName={localappdata}\Programs\VeriNest
DefaultGroupName=VeriNest
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\..\dist
OutputBaseFilename=VeriNest-{#AppVersion}-Setup
SetupIconFile=verinest.ico
UninstallDisplayIcon={app}\VeriNest.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
LicenseFile=..\..\LICENSE

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
Source: "..\..\dist\VeriNest\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\VeriNest"; Filename: "{app}\VeriNest.exe"
Name: "{autodesktop}\VeriNest"; Filename: "{app}\VeriNest.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\VeriNest.exe"; Description: "Launch VeriNest"; Flags: nowait postinstall skipifsilent
