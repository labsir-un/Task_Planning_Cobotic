MODULE MotionPlanningSim
    CONST num gridSize := 10;
    CONST num approachHeightMm := 80;
    CONST orient gridVerticalOrient := [0, 1, 0, 0];
    CONST speeddata vSafeJoint := [50, 50, 50, 50];
    CONST speeddata vSafeApproach := [80, 50, 50, 50];
    CONST speeddata vSafeWork := [40, 30, 30, 30];

    ! Calibration points on the real grid:
    ! (2,0), (7,0), (5,5)
    CONST robtarget pCal20 :=
        [[430, -150, 400], [1, 0, 0, 0], [0, 0, 0, 0], [9E9, 9E9, 9E9, 9E9, 9E9, 9E9]];
    CONST robtarget pCal70 :=
        [[430, 150, 400], [1, 0, 0, 0], [0, 0, 0, 0], [9E9, 9E9, 9E9, 9E9, 9E9, 9E9]];
    CONST robtarget pCal55 :=
        [[730, 30, 400], [1, 0, 0, 0], [0, 0, 0, 0], [9E9, 9E9, 9E9, 9E9, 9E9, 9E9]];

    ! Waiting position in joint space (axis values).
    CONST jointtarget jWaitPos :=
        [[0, -45, 45, 0, 90, 180], [9E9, 9E9, 9E9, 9E9, 9E9, 9E9]];

    VAR num gridX;
    VAR num gridY;
    VAR string dirChar;
    VAR string sx;
    VAR string sy;

    PROC IsValidDirection(string d, VAR bool ok)
        IF d = "U" OR d = "D" OR d = "L" OR d = "R" THEN
            ok := TRUE;
            RETURN;
        ENDIF
        ok := FALSE;
    ENDPROC

    PROC InGrid(num x, num y, VAR bool ok)
        IF x < 0 OR x >= gridSize THEN
            ok := FALSE;
            RETURN;
        ENDIF
        IF y < 0 OR y >= gridSize THEN
            ok := FALSE;
            RETURN;
        ENDIF
        ok := TRUE;
    ENDPROC

    PROC CellCenterTarget(num x, num y, num zOffset, VAR robtarget t)
        VAR num stepXx;
        VAR num stepXy;
        VAR num stepXz;
        VAR num stepYx;
        VAR num stepYy;
        VAR num stepYz;

        t := pCal20;
        ! Force fixed tool orientation on the grid (vertical axis parallel to world Z).
        t.rot := gridVerticalOrient;

        ! X axis per-cell step from (2,0) -> (7,0): divide by 5 cells.
        stepXx := (pCal70.trans.x - pCal20.trans.x) / 5;
        stepXy := (pCal70.trans.y - pCal20.trans.y) / 5;
        stepXz := (pCal70.trans.z - pCal20.trans.z) / 5;

        ! Y axis per-cell step from (2,0) -> (5,5): remove X contribution (3 cells) and divide by 5.
        stepYx := (pCal55.trans.x - pCal20.trans.x - 3 * stepXx) / 5;
        stepYy := (pCal55.trans.y - pCal20.trans.y - 3 * stepXy) / 5;
        stepYz := (pCal55.trans.z - pCal20.trans.z - 3 * stepXz) / 5;

        t.trans.x := pCal20.trans.x + (x - 2) * stepXx + y * stepYx;
        t.trans.y := pCal20.trans.y + (x - 2) * stepXy + y * stepYy;
        t.trans.z := pCal20.trans.z + (x - 2) * stepXz + y * stepYz + zOffset;
    ENDPROC

    PROC ComputeNextCell(num x, num y, string d, VAR num nx, VAR num ny, VAR bool ok)
        VAR bool inRange;
        ok := TRUE;
        nx := x;
        ny := y;

        IF d = "U" THEN
            ny := y - 1;
        ELSEIF d = "D" THEN
            ny := y + 1;
        ELSEIF d = "L" THEN
            nx := x - 1;
        ELSEIF d = "R" THEN
            nx := x + 1;
        ELSE
            ok := FALSE;
            RETURN;
        ENDIF

        InGrid nx, ny, inRange;
        IF NOT inRange THEN
            ok := FALSE;
        ENDIF
    ENDPROC

    PROC MoveOnGrid(num x, num y, string d, VAR bool ok)
        VAR num nextX;
        VAR num nextY;
        VAR bool nextOk;
        VAR robtarget pStartAbove;
        VAR robtarget pStartPlane;
        VAR robtarget pEndPlane;
        VAR robtarget pEndAbove;

        ok := FALSE;
        ComputeNextCell x, y, d, nextX, nextY, nextOk;
        IF NOT nextOk THEN
            RETURN;
        ENDIF

        CellCenterTarget x, y, approachHeightMm, pStartAbove;
        CellCenterTarget x, y, 0, pStartPlane;
        CellCenterTarget nextX, nextY, 0, pEndPlane;
        CellCenterTarget nextX, nextY, approachHeightMm, pEndAbove;

        ! 1) Get close above start cell
        MoveJ pStartAbove, vSafeApproach, z50, tool0\WObj:=wobj0;
        ! 2) Move down to plane
        MoveL pStartPlane, vSafeWork, fine, tool0\WObj:=wobj0;
        ! 3) Move in requested direction on plane
        MoveL pEndPlane, vSafeWork, fine, tool0\WObj:=wobj0;
        ! 4) Move up from plane
        MoveL pEndAbove, vSafeApproach, fine, tool0\WObj:=wobj0;
        ! 5) Stay there
        ok := TRUE;
    ERROR
        ok := FALSE;
        MoveInitPosition;
        RETURN;
    ENDPROC

    PROC MoveInitPosition()
        MoveAbsJ jWaitPos, vSafeJoint, fine, tool0;
    ERROR
        RETURN;
    ENDPROC

    PROC ParsePayload(string s, VAR bool ok)
        VAR bool inRange;
        VAR bool dirOk;
        IF StrLen(s) <> 5 THEN
            ok := FALSE;
            RETURN;
        ENDIF
        sx := StrPart(s, 1, 2);
        sy := StrPart(s, 3, 2);
        dirChar := StrPart(s, 5, 1);
        IF NOT StrToVal(sx, gridX) THEN
            ok := FALSE;
            RETURN;
        ENDIF
        IF NOT StrToVal(sy, gridY) THEN
            ok := FALSE;
            RETURN;
        ENDIF
        InGrid gridX, gridY, inRange;
        IF NOT inRange THEN
            ok := FALSE;
            RETURN;
        ENDIF
        IsValidDirection dirChar, dirOk;
        IF NOT dirOk THEN
            ok := FALSE;
            RETURN;
        ENDIF
        ok := TRUE;
    ENDPROC

    PROC ExecuteCommand(string cmd)
        VAR bool payloadOk;
        VAR bool moveOk;

        IF cmd = "XXXXX" THEN
            TPWrite "Special cmd: move wait";
            MoveInitPosition;
            TPWrite "OK";
            RETURN;
        ENDIF

        ParsePayload cmd, payloadOk;
        IF payloadOk THEN
            TPWrite "Parsed x=";
            TPWrite NumToStr(gridX, 0);
            TPWrite "Parsed y=";
            TPWrite NumToStr(gridY, 0);
            TPWrite "dir=";
            TPWrite dirChar;
            MoveOnGrid gridX, gridY, dirChar, moveOk;
            IF moveOk THEN
                TPWrite "OK";
            ELSE
                MoveInitPosition;
                TPWrite "Invalid move";
            ENDIF
        ELSE
            MoveInitPosition;
            TPWrite "Invalid payload";
        ENDIF
    ERROR
        MoveInitPosition;
        TPWrite "0";
        RETURN;
    ENDPROC

    PROC SweepAllCells()
        VAR num x;
        VAR num y;
        VAR num xi;
        VAR bool rowForward;
        VAR robtarget pAbove;
        VAR robtarget pPlane;

        rowForward := TRUE;
        FOR y FROM 0 TO gridSize - 1 DO
            IF rowForward THEN
                FOR x FROM 0 TO gridSize - 1 DO
                    CellCenterTarget x, y, approachHeightMm, pAbove;
                    CellCenterTarget x, y, 0, pPlane;
                    MoveJ pAbove, vSafeApproach, z50, tool0\WObj:=wobj0;
                    MoveL pPlane, vSafeWork, fine, tool0\WObj:=wobj0;
                    MoveL pAbove, vSafeApproach, fine, tool0\WObj:=wobj0;
                ENDFOR
            ELSE
                FOR x FROM 0 TO gridSize - 1 DO
                    xi := gridSize - 1 - x;
                    CellCenterTarget xi, y, approachHeightMm, pAbove;
                    CellCenterTarget xi, y, 0, pPlane;
                    MoveJ pAbove, vSafeApproach, z50, tool0\WObj:=wobj0;
                    MoveL pPlane, vSafeWork, fine, tool0\WObj:=wobj0;
                    MoveL pAbove, vSafeApproach, fine, tool0\WObj:=wobj0;
                ENDFOR
            ENDIF
            rowForward := NOT rowForward;
        ENDFOR
    ERROR
        MoveInitPosition;
        RETURN;
    ENDPROC

    PROC CalibrateGrid()
        VAR robtarget p20;
        VAR robtarget p70;
        VAR robtarget p55;

        CellCenterTarget 2, 0, 0, p20;
        CellCenterTarget 7, 0, 0, p70;
        CellCenterTarget 5, 5, 0, p55;

        WHILE TRUE DO
            MoveJ p20, vSafeWork, fine, tool0\WObj:=wobj0;
            WaitTime 3;
            MoveJ p70, vSafeWork, fine, tool0\WObj:=wobj0;
            WaitTime 3;
            MoveJ p55, vSafeWork, fine, tool0\WObj:=wobj0;
            WaitTime 3;
        ENDWHILE
    ERROR
        MoveInitPosition;
        RETURN;
    ENDPROC

    PROC main()
        ! CalibrateGrid;
        MoveInitPosition;
        WaitTime 5;

        TPWrite "TEST 1: 0203D";
        ExecuteCommand "0203D";
        WaitTime 5;

        TPWrite "TEST 2: 0504U";
        ExecuteCommand "0504U";
        WaitTime 5;

        TPWrite "TEST 3: 0903L";
        ExecuteCommand "0903L";
        WaitTime 5;

        TPWrite "TEST 4: 0005R";
        ExecuteCommand "0005R";
        WaitTime 5;

        TPWrite "TESTS DONE";
        MoveInitPosition;
        WHILE TRUE DO
            WaitTime 0.1;
        ENDWHILE
    ENDPROC
ENDMODULE

