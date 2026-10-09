"""Administrator-owned session files, independent of the user's temp directory."""
import os
from pathlib import Path
import tempfile


def private_session():
    if os.name!='nt':
        root=Path(tempfile.mkdtemp(prefix='univpn-routes-'));root.chmod(0o700);return root
    import ctypes
    import win32security as security
    # GetWindowsDirectory ignores user-supplied WINDIR/TEMP environment values.
    buffer=ctypes.create_unicode_buffer(32768)
    if not ctypes.windll.kernel32.GetWindowsDirectoryW(buffer,len(buffer)):
        raise ctypes.WinError()
    parent=Path(buffer.value)/'UniVPNConnectSessions'
    descriptor=security.ConvertStringSecurityDescriptorToSecurityDescriptor(
        'O:BAG:BAD:P(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)',security.SDDL_REVISION_1)
    if not parent.exists():
        import win32file
        import pywintypes
        attributes=pywintypes.SECURITY_ATTRIBUTES();attributes.SECURITY_DESCRIPTOR=descriptor
        win32file.CreateDirectory(str(parent),attributes)
    verify_directory(parent)
    root=Path(tempfile.mkdtemp(prefix='session-',dir=parent))
    security.SetFileSecurity(str(root),security.OWNER_SECURITY_INFORMATION|
                             security.DACL_SECURITY_INFORMATION|
                             security.PROTECTED_DACL_SECURITY_INFORMATION,descriptor)
    verify_directory(root);return root


def verify_directory(path):
    if os.name!='nt':return
    import win32security as security
    import win32file
    attributes=win32file.GetFileAttributes(str(path))
    if attributes&0x400:raise ValueError('Reparse points are not allowed in route sessions')
    sd=security.GetFileSecurity(str(path),security.OWNER_SECURITY_INFORMATION|security.DACL_SECURITY_INFORMATION)
    allowed={'S-1-5-18','S-1-5-32-544'}
    if security.ConvertSidToStringSid(sd.GetSecurityDescriptorOwner()) not in allowed:
        raise ValueError('Route session must be owned by Administrators or SYSTEM')
    acl=sd.GetSecurityDescriptorDacl()
    if acl is None:raise ValueError('Missing route session ACL')
    for i in range(acl.GetAceCount()):
        header,mask,sid=acl.GetAce(i)
        if header[0]!=security.ACCESS_ALLOWED_ACE_TYPE or security.ConvertSidToStringSid(sid) not in allowed:
            raise ValueError('Route session ACL allows an unexpected principal')
