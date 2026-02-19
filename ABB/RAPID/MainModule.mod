MODULE MotionPlanning
    CONST string ipController := "192.168.125.1";
    VAR socketdev serverSocket;
    VAR socketdev clientSocket;
    VAR bool clientConnected;
    CONST num port := 8000;

    VAR num gridX;
    VAR num gridY;
    VAR string dirChar;
    VAR string sx;
    VAR string sy;

    PROC SendReply(string msg)
        SocketSend clientSocket \str := msg;
    ENDPROC

    FUNC bool ParsePayload(string s)
        IF StrLen(s) <> 5 THEN
            RETURN FALSE;
        ENDIF
        sx := StrPart(s, 1, 2);
        sy := StrPart(s, 3, 2);
        dirChar := StrPart(s, 5, 1);
        IF NOT StrToVal(sx, gridX) THEN
            RETURN FALSE;
        ENDIF
        IF NOT StrToVal(sy, gridY) THEN
            RETURN FALSE;
        ENDIF
        RETURN TRUE;
    ENDFUNC

    PROC HandleCommand()
        VAR string clientData;
        SocketReceive clientSocket \str := clientData \Time:=60;
        TPWrite "Received: " \Str:=clientData;
        IF ParsePayload(clientData) THEN
            TPWrite "Parsed x=" \Num:=gridX, ", y=" \Num:=gridY, ", dir=" \Str:=dirChar;
            ! TODO: map gridX,gridY,dirChar to world coords and execute motion
            SendReply("1");
        ELSE
            SendReply("0");
        ENDIF
    ENDPROC

    PROC SocketDisconnection()
        IF clientConnected THEN
            SocketClose clientSocket;
        ENDIF
        SocketClose serverSocket;
        clientConnected := FALSE;
    ENDPROC

    PROC SocketConnection()
        SocketCreate serverSocket;
        SocketBind serverSocket, ipController, port;
        SocketListen serverSocket;
        SocketAccept serverSocket, clientSocket, \Time := 60;
        clientConnected := TRUE;
        SocketSend clientSocket \str := "Success";
    ENDPROC

    PROC main()
        SocketDisconnection;
        WHILE TRUE DO
            IF NOT clientConnected THEN
                SocketConnection;
            ELSE
                HandleCommand;
            ENDIF
        ENDWHILE
    ENDPROC
ENDMODULE
