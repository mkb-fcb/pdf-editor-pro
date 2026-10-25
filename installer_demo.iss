#define MyAppName "PDF Editör Pro Demo"
#define MyAppVersion "1.0.7"
#define MyAppPublisher "FB Tekstil"
#define MyAppURL "https://www.mkbsoft.net"
#define MyAppExeName "PDFEditor.exe"
#define MyAppId "{{B7D2E4F1-9C6A-4E8B-A1D3-5F2C7B8D9E0A}"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} v{#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\PDFEditorProDemo
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=C:\Users\kamil.bilir\pdf_editor\installer_output
OutputBaseFilename=PDFEditorPro_Demo_v{#MyAppVersion}
SetupIconFile=C:\Users\kamil.bilir\pdf_editor\icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
WizardResizable=no
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName} v{#MyAppVersion}
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} - Ücretsiz Demo
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Masaüstüne kısayol oluştur"; GroupDescription: "Ek seçenekler:"; Flags: checkedonce

[InstallDelete]
; v1.0.4 öncesi demo ayrı bir exe idi (PDFEditorDemo.exe); artık tam sürümle aynı program demo modunda açılıyor
Type: files; Name: "{app}\PDFEditorDemo.exe"

[Files]
Source: "C:\Users\kamil.bilir\pdf_editor\dist\PDFEditor\PDFEditor.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "C:\Users\kamil.bilir\pdf_editor\dist\PDFEditor\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{#MyAppName} Kaldır"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "PDF Editör Pro Demo'yu şimdi başlat"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: dirifempty; Name: "{app}"
