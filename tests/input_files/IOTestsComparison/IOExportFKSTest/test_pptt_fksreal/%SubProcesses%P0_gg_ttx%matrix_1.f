      SUBROUTINE SMATRIX_1(P,ANS)
C     
C     Generated by MadGraph5_aMC@NLO v. %(version)s, %(date)s
C     By the MadGraph5_aMC@NLO Development Team
C     Visit launchpad.net/madgraph5 and amcatnlo.web.cern.ch
C     
C     Returns amplitude squared summed/avg over colors
C     and helicities
C     for the point in phase space P(0:3,NEXTERNAL)
C     
C     Process: g g > t t~ g WEIGHTED<=3 [ real = QCD ]
C     
      IMPLICIT NONE
C     
C     CONSTANTS
C     
      INCLUDE 'nexternal.inc'
      INTEGER     NCOMB
      PARAMETER ( NCOMB=32)
C     
C     ARGUMENTS 
C     
      REAL*8 P(0:3,NEXTERNAL),ANS
      DOUBLE PRECISION       WGT_ME_BORN,WGT_ME_REAL
      COMMON /C_WGT_ME_TREE/ WGT_ME_BORN,WGT_ME_REAL
C     
C     LOCAL VARIABLES 
C     
      INTEGER IHEL,IDEN,I,T_IDENT(NCOMB)
      REAL*8 MATRIX_1
      REAL*8 T,T_SAVE(NCOMB)
      SAVE T_SAVE,T_IDENT
      INTEGER NHEL(NEXTERNAL,NCOMB)
      DATA (NHEL(I,   1),I=1,5) /-1,-1,-1, 1,-1/
      DATA (NHEL(I,   2),I=1,5) /-1,-1,-1, 1, 1/
      DATA (NHEL(I,   3),I=1,5) /-1,-1,-1,-1,-1/
      DATA (NHEL(I,   4),I=1,5) /-1,-1,-1,-1, 1/
      DATA (NHEL(I,   5),I=1,5) /-1,-1, 1, 1,-1/
      DATA (NHEL(I,   6),I=1,5) /-1,-1, 1, 1, 1/
      DATA (NHEL(I,   7),I=1,5) /-1,-1, 1,-1,-1/
      DATA (NHEL(I,   8),I=1,5) /-1,-1, 1,-1, 1/
      DATA (NHEL(I,   9),I=1,5) /-1, 1,-1, 1,-1/
      DATA (NHEL(I,  10),I=1,5) /-1, 1,-1, 1, 1/
      DATA (NHEL(I,  11),I=1,5) /-1, 1,-1,-1,-1/
      DATA (NHEL(I,  12),I=1,5) /-1, 1,-1,-1, 1/
      DATA (NHEL(I,  13),I=1,5) /-1, 1, 1, 1,-1/
      DATA (NHEL(I,  14),I=1,5) /-1, 1, 1, 1, 1/
      DATA (NHEL(I,  15),I=1,5) /-1, 1, 1,-1,-1/
      DATA (NHEL(I,  16),I=1,5) /-1, 1, 1,-1, 1/
      DATA (NHEL(I,  17),I=1,5) / 1,-1,-1, 1,-1/
      DATA (NHEL(I,  18),I=1,5) / 1,-1,-1, 1, 1/
      DATA (NHEL(I,  19),I=1,5) / 1,-1,-1,-1,-1/
      DATA (NHEL(I,  20),I=1,5) / 1,-1,-1,-1, 1/
      DATA (NHEL(I,  21),I=1,5) / 1,-1, 1, 1,-1/
      DATA (NHEL(I,  22),I=1,5) / 1,-1, 1, 1, 1/
      DATA (NHEL(I,  23),I=1,5) / 1,-1, 1,-1,-1/
      DATA (NHEL(I,  24),I=1,5) / 1,-1, 1,-1, 1/
      DATA (NHEL(I,  25),I=1,5) / 1, 1,-1, 1,-1/
      DATA (NHEL(I,  26),I=1,5) / 1, 1,-1, 1, 1/
      DATA (NHEL(I,  27),I=1,5) / 1, 1,-1,-1,-1/
      DATA (NHEL(I,  28),I=1,5) / 1, 1,-1,-1, 1/
      DATA (NHEL(I,  29),I=1,5) / 1, 1, 1, 1,-1/
      DATA (NHEL(I,  30),I=1,5) / 1, 1, 1, 1, 1/
      DATA (NHEL(I,  31),I=1,5) / 1, 1, 1,-1,-1/
      DATA (NHEL(I,  32),I=1,5) / 1, 1, 1,-1, 1/
      LOGICAL GOODHEL(NCOMB)
      DATA GOODHEL/NCOMB*.FALSE./
      INTEGER NTRY
      DATA NTRY/0/
      DATA IDEN/256/
C     ----------
C     BEGIN CODE
C     ----------
      NTRY=NTRY+1
      ANS = 0D0
      DO IHEL=1,NCOMB
        IF (GOODHEL(IHEL) .OR. NTRY .LT. 2) THEN
          IF (NTRY.LT.2) THEN
C           for the first ps-point, check for helicities that give
C           identical matrix elements
            T=MATRIX_1(P ,NHEL(1,IHEL))
            T_SAVE(IHEL)=T
            T_IDENT(IHEL)=-1
            DO I=1,IHEL-1
              IF (T.EQ.0D0) EXIT
              IF (T_SAVE(I).EQ.0D0) CYCLE
              IF (ABS(T/T_SAVE(I)-1D0) .LT. 1D-12) THEN
C               WRITE (*,*) 'FOUND IDENTICAL',T,IHEL,T_SAVE(I),I
                T_IDENT(IHEL) = I
              ENDIF
            ENDDO
          ELSE
            IF (T_IDENT(IHEL).GT.0) THEN
C             if two helicity states are identical, dont recompute
              T=T_SAVE(T_IDENT(IHEL))
              T_SAVE(IHEL)=T
            ELSE
              T=MATRIX_1(P ,NHEL(1,IHEL))
              T_SAVE(IHEL)=T
            ENDIF
          ENDIF
C         add to the sum of helicities
          ANS=ANS+T
          IF (T .NE. 0D0 .AND. .NOT. GOODHEL(IHEL)) THEN
            GOODHEL(IHEL)=.TRUE.
          ENDIF
        ENDIF
      ENDDO
      ANS=ANS/DBLE(IDEN)
      WGT_ME_REAL=ANS
      END


      REAL*8 FUNCTION MATRIX_1(P,NHEL)
C     
C     Generated by MadGraph5_aMC@NLO v. %(version)s, %(date)s
C     By the MadGraph5_aMC@NLO Development Team
C     Visit launchpad.net/madgraph5 and amcatnlo.web.cern.ch
C     
C     Returns amplitude squared summed/avg over colors
C     for the point with external lines W(0:6,NEXTERNAL)
C     
C     Process: g g > t t~ g WEIGHTED<=3 [ real = QCD ]
C     
      IMPLICIT NONE
C     
C     CONSTANTS
C     
      INTEGER    NGRAPHS
      PARAMETER (NGRAPHS=18)
      INTEGER    NWAVEFUNCS, NCOLOR
      PARAMETER (NWAVEFUNCS=12, NCOLOR=6)
      REAL*8     ZERO
      PARAMETER (ZERO=0D0)
      COMPLEX*16 IMAG1
      PARAMETER (IMAG1=(0D0,1D0))
      INCLUDE 'nexternal.inc'
      INCLUDE 'coupl.inc'
C     
C     ARGUMENTS 
C     
      REAL*8 P(0:3,NEXTERNAL)
      INTEGER NHEL(NEXTERNAL)
C     
C     LOCAL VARIABLES 
C     
      INTEGER I,J
      INTEGER IC(NEXTERNAL)
      DATA IC /NEXTERNAL*1/
      REAL*8 DENOM(NCOLOR), CF(NCOLOR,NCOLOR)
      COMPLEX*16 ZTEMP, AMP(NGRAPHS), JAMP(NCOLOR), W(8,NWAVEFUNCS)
C     
C     COLOR DATA
C     
      DATA DENOM(1)/9/
      DATA (CF(I,  1),I=  1,  6) /   64,   -8,   -8,    1,    1,   10/
C     1 T(1,2,5,3,4)
      DATA DENOM(2)/9/
      DATA (CF(I,  2),I=  1,  6) /   -8,   64,    1,   10,   -8,    1/
C     1 T(1,5,2,3,4)
      DATA DENOM(3)/9/
      DATA (CF(I,  3),I=  1,  6) /   -8,    1,   64,   -8,   10,    1/
C     1 T(2,1,5,3,4)
      DATA DENOM(4)/9/
      DATA (CF(I,  4),I=  1,  6) /    1,   10,   -8,   64,    1,   -8/
C     1 T(2,5,1,3,4)
      DATA DENOM(5)/9/
      DATA (CF(I,  5),I=  1,  6) /    1,   -8,   10,    1,   64,   -8/
C     1 T(5,1,2,3,4)
      DATA DENOM(6)/9/
      DATA (CF(I,  6),I=  1,  6) /   10,    1,    1,   -8,   -8,   64/
C     1 T(5,2,1,3,4)
C     ----------
C     BEGIN CODE
C     ----------
      CALL VXXXXX(P(0,1),ZERO,NHEL(1),-1*IC(1),W(1,1))
      CALL VXXXXX(P(0,2),ZERO,NHEL(2),-1*IC(2),W(1,2))
      CALL OXXXXX(P(0,3),MDL_MT,NHEL(3),+1*IC(3),W(1,3))
      CALL IXXXXX(P(0,4),MDL_MT,NHEL(4),-1*IC(4),W(1,4))
      CALL VXXXXX(P(0,5),ZERO,NHEL(5),+1*IC(5),W(1,5))
      CALL VVV1P0_1(W(1,1),W(1,2),GC_10,ZERO,ZERO,W(1,6))
      CALL FFV1P0_3(W(1,4),W(1,3),GC_11,ZERO,ZERO,W(1,7))
C     Amplitude(s) for diagram number 1
      CALL VVV1_0(W(1,6),W(1,7),W(1,5),GC_10,AMP(1))
      CALL FFV1_1(W(1,3),W(1,5),GC_11,MDL_MT,MDL_WT,W(1,8))
C     Amplitude(s) for diagram number 2
      CALL FFV1_0(W(1,4),W(1,8),W(1,6),GC_11,AMP(2))
      CALL FFV1_2(W(1,4),W(1,5),GC_11,MDL_MT,MDL_WT,W(1,9))
C     Amplitude(s) for diagram number 3
      CALL FFV1_0(W(1,9),W(1,3),W(1,6),GC_11,AMP(3))
      CALL FFV1_1(W(1,3),W(1,1),GC_11,MDL_MT,MDL_WT,W(1,6))
      CALL FFV1_2(W(1,4),W(1,2),GC_11,MDL_MT,MDL_WT,W(1,10))
C     Amplitude(s) for diagram number 4
      CALL FFV1_0(W(1,10),W(1,6),W(1,5),GC_11,AMP(4))
      CALL VVV1P0_1(W(1,2),W(1,5),GC_10,ZERO,ZERO,W(1,11))
C     Amplitude(s) for diagram number 5
      CALL FFV1_0(W(1,4),W(1,6),W(1,11),GC_11,AMP(5))
C     Amplitude(s) for diagram number 6
      CALL FFV1_0(W(1,9),W(1,6),W(1,2),GC_11,AMP(6))
      CALL FFV1_2(W(1,4),W(1,1),GC_11,MDL_MT,MDL_WT,W(1,6))
      CALL FFV1_1(W(1,3),W(1,2),GC_11,MDL_MT,MDL_WT,W(1,12))
C     Amplitude(s) for diagram number 7
      CALL FFV1_0(W(1,6),W(1,12),W(1,5),GC_11,AMP(7))
C     Amplitude(s) for diagram number 8
      CALL FFV1_0(W(1,6),W(1,3),W(1,11),GC_11,AMP(8))
C     Amplitude(s) for diagram number 9
      CALL FFV1_0(W(1,6),W(1,8),W(1,2),GC_11,AMP(9))
      CALL VVV1P0_1(W(1,1),W(1,5),GC_10,ZERO,ZERO,W(1,6))
C     Amplitude(s) for diagram number 10
      CALL FFV1_0(W(1,4),W(1,12),W(1,6),GC_11,AMP(10))
C     Amplitude(s) for diagram number 11
      CALL FFV1_0(W(1,10),W(1,3),W(1,6),GC_11,AMP(11))
C     Amplitude(s) for diagram number 12
      CALL VVV1_0(W(1,6),W(1,2),W(1,7),GC_10,AMP(12))
C     Amplitude(s) for diagram number 13
      CALL FFV1_0(W(1,9),W(1,12),W(1,1),GC_11,AMP(13))
C     Amplitude(s) for diagram number 14
      CALL FFV1_0(W(1,10),W(1,8),W(1,1),GC_11,AMP(14))
C     Amplitude(s) for diagram number 15
      CALL VVV1_0(W(1,1),W(1,11),W(1,7),GC_10,AMP(15))
      CALL VVVV1P0_1(W(1,1),W(1,2),W(1,5),GC_12,ZERO,ZERO,W(1,11))
      CALL VVVV3P0_1(W(1,1),W(1,2),W(1,5),GC_12,ZERO,ZERO,W(1,7))
      CALL VVVV4P0_1(W(1,1),W(1,2),W(1,5),GC_12,ZERO,ZERO,W(1,10))
C     Amplitude(s) for diagram number 16
      CALL FFV1_0(W(1,4),W(1,3),W(1,11),GC_11,AMP(16))
      CALL FFV1_0(W(1,4),W(1,3),W(1,7),GC_11,AMP(17))
      CALL FFV1_0(W(1,4),W(1,3),W(1,10),GC_11,AMP(18))
      JAMP(1)=-AMP(1)+IMAG1*AMP(3)+IMAG1*AMP(5)-AMP(6)+AMP(15)+AMP(16)
     $ -AMP(18)
      JAMP(2)=-AMP(4)-IMAG1*AMP(5)+IMAG1*AMP(11)+AMP(12)-AMP(15)
     $ -AMP(16)-AMP(17)
      JAMP(3)=+AMP(1)-IMAG1*AMP(3)+IMAG1*AMP(10)-AMP(12)-AMP(13)
     $ +AMP(17)+AMP(18)
      JAMP(4)=-AMP(7)+IMAG1*AMP(8)-IMAG1*AMP(10)+AMP(12)-AMP(15)
     $ -AMP(16)-AMP(17)
      JAMP(5)=+AMP(1)+IMAG1*AMP(2)-IMAG1*AMP(11)-AMP(12)-AMP(14)
     $ +AMP(17)+AMP(18)
      JAMP(6)=-AMP(1)-IMAG1*AMP(2)-IMAG1*AMP(8)-AMP(9)+AMP(15)+AMP(16)
     $ -AMP(18)
      MATRIX_1 = 0.D0
      DO I = 1, NCOLOR
        ZTEMP = (0.D0,0.D0)
        DO J = 1, NCOLOR
          ZTEMP = ZTEMP + CF(J,I)*JAMP(J)
        ENDDO
        MATRIX_1 = MATRIX_1+ZTEMP*DCONJG(JAMP(I))/DENOM(I)
      ENDDO
      END

