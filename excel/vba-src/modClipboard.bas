Attribute VB_Name = "modClipboard"
Option Explicit

' =====================================================================
' modClipboard - Unicode-Zwischenablage ueber Win32-API (Office x64:
' alle Deklarationen PtrSafe, Handles/Pointer als LongPtr).
' =====================================================================

#If VBA7 Then
    Private Declare PtrSafe Function OpenClipboard Lib "user32" (ByVal hwnd As LongPtr) As Long
    Private Declare PtrSafe Function CloseClipboard Lib "user32" () As Long
    Private Declare PtrSafe Function EmptyClipboard Lib "user32" () As Long
    Private Declare PtrSafe Function SetClipboardData Lib "user32" (ByVal uFormat As Long, ByVal hMem As LongPtr) As LongPtr
    Private Declare PtrSafe Function GlobalAlloc Lib "kernel32" (ByVal uFlags As Long, ByVal dwBytes As LongPtr) As LongPtr
    Private Declare PtrSafe Function GlobalLock Lib "kernel32" (ByVal hMem As LongPtr) As LongPtr
    Private Declare PtrSafe Function GlobalUnlock Lib "kernel32" (ByVal hMem As LongPtr) As Long
    Private Declare PtrSafe Function GlobalFree Lib "kernel32" (ByVal hMem As LongPtr) As LongPtr
    Private Declare PtrSafe Function lstrcpyW Lib "kernel32" (ByVal lpString1 As LongPtr, ByVal lpString2 As LongPtr) As LongPtr
#Else
    Private Declare Function OpenClipboard Lib "user32" (ByVal hwnd As Long) As Long
    Private Declare Function CloseClipboard Lib "user32" () As Long
    Private Declare Function EmptyClipboard Lib "user32" () As Long
    Private Declare Function SetClipboardData Lib "user32" (ByVal uFormat As Long, ByVal hMem As Long) As Long
    Private Declare Function GlobalAlloc Lib "kernel32" (ByVal uFlags As Long, ByVal dwBytes As Long) As Long
    Private Declare Function GlobalLock Lib "kernel32" (ByVal hMem As Long) As Long
    Private Declare Function GlobalUnlock Lib "kernel32" (ByVal hMem As Long) As Long
    Private Declare Function GlobalFree Lib "kernel32" (ByVal hMem As Long) As Long
    Private Declare Function lstrcpyW Lib "kernel32" (ByVal lpString1 As Long, ByVal lpString2 As Long) As Long
#End If

Private Const GMEM_MOVEABLE As Long = &H2
Private Const CF_UNICODETEXT As Long = 13

Public Function SetClipboardText(ByVal text As String) As Boolean
    #If VBA7 Then
        Dim hMem As LongPtr, pMem As LongPtr
        Dim byteLen As LongPtr
    #Else
        Dim hMem As Long, pMem As Long
        Dim byteLen As Long
    #End If
    Dim ok As Boolean

    byteLen = (Len(text) + 1) * 2
    If OpenClipboard(0) = 0 Then
        SetClipboardText = False
        Exit Function
    End If
    On Error GoTo cleanup
    EmptyClipboard
    hMem = GlobalAlloc(GMEM_MOVEABLE, byteLen)
    If hMem <> 0 Then
        pMem = GlobalLock(hMem)
        If pMem <> 0 Then
            lstrcpyW pMem, StrPtr(text)
            GlobalUnlock hMem
            If SetClipboardData(CF_UNICODETEXT, hMem) <> 0 Then
                ok = True       ' Ownership liegt jetzt beim System
            Else
                GlobalFree hMem
            End If
        Else
            GlobalFree hMem
        End If
    End If
cleanup:
    CloseClipboard
    SetClipboardText = ok
End Function
