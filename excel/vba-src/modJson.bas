Attribute VB_Name = "modJson"
Option Explicit

' =====================================================================
' modJson - kompakter JSON-Parser/-Builder (UTF-16-VBA-Strings)
' Objekte -> Scripting.Dictionary, Arrays -> Collection.
' Nur fuer die eigenen, versionierten Kernvertraege gedacht.
' =====================================================================

Private mText As String
Private mPos As Long

Public Function ParseJson(ByVal jsonText As String) As Object
    mText = jsonText
    mPos = 1
    SkipWs
    Set ParseJson = ParseValue()
End Function

Private Function ParseValue() As Variant
    Dim ch As String
    SkipWs
    ch = Peek()
    Select Case ch
        Case "{"
            Set ParseValue = ParseObject()
        Case "["
            Set ParseValue = ParseArray()
        Case """"
            ParseValue = ParseString()
        Case "t"
            Expect "true": ParseValue = True
        Case "f"
            Expect "false": ParseValue = False
        Case "n"
            Expect "null": ParseValue = Null
        Case Else
            ParseValue = ParseNumber()
    End Select
End Function

Private Function ParseObject() As Object
    Dim d As Object, key As String
    Set d = CreateObject("Scripting.Dictionary")
    d.CompareMode = 0 ' BinaryCompare: Schluessel sind case-sensitiv
    ExpectChar "{"
    SkipWs
    If Peek() = "}" Then
        mPos = mPos + 1
        Set ParseObject = d
        Exit Function
    End If
    Do
        SkipWs
        key = ParseString()
        SkipWs
        ExpectChar ":"
        SkipWs
        AssignValue d, key
        SkipWs
        If Peek() = "," Then
            mPos = mPos + 1
        ElseIf Peek() = "}" Then
            mPos = mPos + 1
            Exit Do
        Else
            Err.Raise vbObjectError + 601, "modJson", "Objekt: ',' oder '}' erwartet an Position " & mPos
        End If
    Loop
    Set ParseObject = d
End Function

Private Sub AssignValue(ByVal d As Object, ByVal key As String)
    Dim v As Variant
    If Peek() = "{" Or Peek() = "[" Then
        Set v = ParseValue()
        Set d(key) = v
    Else
        v = ParseValue()
        d(key) = v
    End If
End Sub

Private Function ParseArray() As Collection
    Dim c As New Collection
    ExpectChar "["
    SkipWs
    If Peek() = "]" Then
        mPos = mPos + 1
        Set ParseArray = c
        Exit Function
    End If
    Do
        SkipWs
        If Peek() = "{" Or Peek() = "[" Then
            c.Add ParseValue()
        Else
            c.Add ParseValue()
        End If
        SkipWs
        If Peek() = "," Then
            mPos = mPos + 1
        ElseIf Peek() = "]" Then
            mPos = mPos + 1
            Exit Do
        Else
            Err.Raise vbObjectError + 602, "modJson", "Array: ',' oder ']' erwartet an Position " & mPos
        End If
    Loop
    Set ParseArray = c
End Function

Private Function ParseString() As String
    Dim sb As String, ch As String, code As String
    ExpectChar """"
    Do While mPos <= Len(mText)
        ch = Mid$(mText, mPos, 1)
        mPos = mPos + 1
        If ch = """" Then
            ParseString = sb
            Exit Function
        ElseIf ch = "\" Then
            ch = Mid$(mText, mPos, 1)
            mPos = mPos + 1
            Select Case ch
                Case """": sb = sb & """"
                Case "\": sb = sb & "\"
                Case "/": sb = sb & "/"
                Case "b": sb = sb & Chr$(8)
                Case "f": sb = sb & Chr$(12)
                Case "n": sb = sb & vbLf
                Case "r": sb = sb & vbCr
                Case "t": sb = sb & vbTab
                Case "u"
                    code = Mid$(mText, mPos, 4)
                    mPos = mPos + 4
                    sb = sb & ChrW$(CLng("&H" & code))
                Case Else
                    Err.Raise vbObjectError + 603, "modJson", "Unbekannte Escape-Sequenz \" & ch
            End Select
        Else
            sb = sb & ch
        End If
    Loop
    Err.Raise vbObjectError + 604, "modJson", "String nicht terminiert"
End Function

Private Function ParseNumber() As Variant
    Dim startPos As Long, ch As String, s As String
    startPos = mPos
    Do While mPos <= Len(mText)
        ch = Mid$(mText, mPos, 1)
        If InStr("0123456789+-.eE", ch) > 0 Then
            mPos = mPos + 1
        Else
            Exit Do
        End If
    Loop
    s = Mid$(mText, startPos, mPos - startPos)
    If InStr(s, ".") > 0 Or InStr(LCase$(s), "e") > 0 Then
        ParseNumber = Val(s)
    Else
        ParseNumber = CDbl(Val(s))
        If Abs(ParseNumber) <= 2147483647 Then ParseNumber = CLng(ParseNumber)
    End If
End Function

Private Function Peek() As String
    If mPos > Len(mText) Then
        Peek = ""
    Else
        Peek = Mid$(mText, mPos, 1)
    End If
End Function

Private Sub ExpectChar(ByVal ch As String)
    If Peek() <> ch Then Err.Raise vbObjectError + 605, "modJson", "'" & ch & "' erwartet an Position " & mPos
    mPos = mPos + 1
End Sub

Private Sub Expect(ByVal word As String)
    If Mid$(mText, mPos, Len(word)) <> word Then
        Err.Raise vbObjectError + 606, "modJson", "'" & word & "' erwartet an Position " & mPos
    End If
    mPos = mPos + Len(word)
End Sub

Private Sub SkipWs()
    Dim ch As String
    Do While mPos <= Len(mText)
        ch = Mid$(mText, mPos, 1)
        If ch = " " Or ch = vbTab Or ch = vbCr Or ch = vbLf Then
            mPos = mPos + 1
        Else
            Exit Do
        End If
    Loop
End Sub

' ------------------------------------------------------------ Builder

Public Function JStr(ByVal s As String) As String
    Dim i As Long, ch As String, code As Long, sb As String
    sb = """"
    For i = 1 To Len(s)
        ch = Mid$(s, i, 1)
        code = AscW(ch)
        Select Case ch
            Case """": sb = sb & "\"""
            Case "\": sb = sb & "\\"
            Case vbCr: sb = sb & "\r"
            Case vbLf: sb = sb & "\n"
            Case vbTab: sb = sb & "\t"
            Case Else
                If code >= 0 And code < 32 Then
                    sb = sb & "\u" & Right$("0000" & Hex$(code), 4)
                Else
                    sb = sb & ch
                End If
        End Select
    Next i
    JStr = sb & """"
End Function

Public Function JBool(ByVal b As Boolean) As String
    JBool = IIf(b, "true", "false")
End Function

Public Function DictGetStr(ByVal d As Object, ByVal key As String, Optional ByVal fallback As String = "") As String
    If d Is Nothing Then
        DictGetStr = fallback
    ElseIf d.Exists(key) Then
        If IsNull(d(key)) Then
            DictGetStr = fallback
        Else
            DictGetStr = CStr(d(key))
        End If
    Else
        DictGetStr = fallback
    End If
End Function

Public Function DictGetBool(ByVal d As Object, ByVal key As String, Optional ByVal fallback As Boolean = False) As Boolean
    If d Is Nothing Then
        DictGetBool = fallback
    ElseIf d.Exists(key) Then
        If IsNull(d(key)) Then
            DictGetBool = fallback
        Else
            DictGetBool = CBool(d(key))
        End If
    Else
        DictGetBool = fallback
    End If
End Function
