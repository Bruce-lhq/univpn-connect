Unicode true
!include "MUI2.nsh"
Name "UniVPN Connect"
!define MUI_ICON "${ICON}"
!define MUI_UNICON "${ICON}"
OutFile "${OUTPUT}"
InstallDir "$PROGRAMFILES64\UniVPN Connect"
RequestExecutionLevel admin
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"
Section "Client"
  SetOutPath "$INSTDIR"
  File /r "${SOURCE}\*"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  CreateDirectory "$SMPROGRAMS\UniVPN Connect"
  CreateShortcut "$SMPROGRAMS\UniVPN Connect\UniVPN Connect.lnk" "$SYSDIR\wscript.exe" '"$INSTDIR\UniVPN Connect.vbs"' "$INSTDIR\UniVPN Connect.exe" 0
  CreateShortcut "$SMPROGRAMS\UniVPN Connect\Uninstall.lnk" "$INSTDIR\Uninstall.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\UniVPNConnect" "DisplayName" "UniVPN Connect"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\UniVPNConnect" "DisplayVersion" "${VERSION}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\UniVPNConnect" "UninstallString" '"$INSTDIR\Uninstall.exe"'
SectionEnd
Section "Uninstall"
  # User profiles and system credential entries are deliberately retained.
  RMDir /r "$INSTDIR"
  RMDir /r "$SMPROGRAMS\UniVPN Connect"
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\UniVPNConnect"
SectionEnd
