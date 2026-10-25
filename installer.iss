#define MyAppName "PDF Editör Pro"
#define MyAppVersion "1.0.7"
#define MyAppPublisher "FB Tekstil"
#define MyAppURL "https://www.mkbsoft.net"
#define MyAppExeName "PDFEditor.exe"
#define MyAppId "{{A3F8C2D1-7B4E-4F9A-8C3D-2E1F5A6B7C8D}"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} v{#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\PDFEditorPro
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=C:\Users\kamil.bilir\pdf_editor\installer_output
OutputBaseFilename=PDFEditorPro_Kurulum_v{#MyAppVersion}
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
VersionInfoDescription={#MyAppName} - PDF Düzenleme Uygulaması
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Masaüstüne kısayol oluştur"; GroupDescription: "Ek seçenekler:"; Flags: checkedonce
Name: "pdfassoc"; Description: "PDF dosyalarını bu uygulama ile aç"; GroupDescription: "Ek seçenekler:"; Flags: unchecked

[Files]
Source: "C:\Users\kamil.bilir\pdf_editor\dist\PDFEditor\PDFEditor.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "C:\Users\kamil.bilir\pdf_editor\dist\PDFEditor\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{#MyAppName} Kaldır"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; PDF dosya ilişkilendirmesi (isteğe bağlı)
Root: HKCU; Subkey: "Software\Classes\.pdf\OpenWithProgids"; ValueType: string; ValueName: "PDFEditorPro.Document"; ValueData: ""; Flags: uninsdeletevalue; Tasks: pdfassoc
Root: HKCU; Subkey: "Software\Classes\PDFEditorPro.Document"; ValueType: string; ValueName: ""; ValueData: "PDF Dosyası"; Flags: uninsdeletekey; Tasks: pdfassoc
Root: HKCU; Subkey: "Software\Classes\PDFEditorPro.Document\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExeName},0"; Tasks: pdfassoc
Root: HKCU; Subkey: "Software\Classes\PDFEditorPro.Document\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Tasks: pdfassoc

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "PDF Editör Pro'yu şimdi başlat"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: dirifempty; Name: "{app}"
