      SUBROUTINE COEF_CONSTRUCTION_1(P,NHEL,H,IC)
C     
C     Modules
C     
      USE POLYNOMIAL_CONSTANTS
C     
      IMPLICIT NONE
C     
C     CONSTANTS
C     
      INTEGER    NEXTERNAL
      PARAMETER (NEXTERNAL=3)
      INTEGER    NCOMB
      PARAMETER (NCOMB=12)
      INTEGER NBORNAMPS
      PARAMETER (NBORNAMPS=1)
      INTEGER    NLOOPS, NLOOPGROUPS, NCTAMPS
      PARAMETER (NLOOPS=1, NLOOPGROUPS=1, NCTAMPS=1)
      INTEGER    NLOOPAMPS
      PARAMETER (NLOOPAMPS=2)
      INTEGER    NWAVEFUNCS,NLOOPWAVEFUNCS
      PARAMETER (NWAVEFUNCS=3,NLOOPWAVEFUNCS=3)
      REAL*8     ZERO
      PARAMETER (ZERO=0D0)
      REAL*16     MP__ZERO
      PARAMETER (MP__ZERO=0.0E0_16)
C     These are constants related to the split orders
      INTEGER    NSO, NSQUAREDSO, NAMPSO
      PARAMETER (NSO=1, NSQUAREDSO=1, NAMPSO=2)
C     
C     ARGUMENTS
C     
      REAL*8 P(0:3,NEXTERNAL)
      INTEGER NHEL(NEXTERNAL), IC(NEXTERNAL)
      INTEGER H
C     
C     LOCAL VARIABLES
C     
      INTEGER I,J,K
      COMPLEX*16 COEFS(MAXLWFSIZE,0:VERTEXMAXCOEFS-1,MAXLWFSIZE)

      LOGICAL DUMMYFALSE
      DATA DUMMYFALSE/.FALSE./
C     
C     GLOBAL VARIABLES
C     
      INCLUDE 'coupl.inc'
      INCLUDE 'mp_coupl.inc'

      INTEGER HELOFFSET
      INTEGER GOODHEL(NCOMB)
      LOGICAL GOODAMP(NSQUAREDSO,NLOOPGROUPS)
      COMMON/FILTERS/GOODAMP,GOODHEL,HELOFFSET

      LOGICAL CHECKPHASE
      LOGICAL HELDOUBLECHECKED
      COMMON/INIT/CHECKPHASE, HELDOUBLECHECKED

      INTEGER SQSO_TARGET
      COMMON/SOCHOICE/SQSO_TARGET

      LOGICAL UVCT_REQ_SO_DONE,MP_UVCT_REQ_SO_DONE,CT_REQ_SO_DONE
     $ ,MP_CT_REQ_SO_DONE,LOOP_REQ_SO_DONE,MP_LOOP_REQ_SO_DONE
     $ ,CTCALL_REQ_SO_DONE,FILTER_SO
      COMMON/SO_REQS/UVCT_REQ_SO_DONE,MP_UVCT_REQ_SO_DONE
     $ ,CT_REQ_SO_DONE,MP_CT_REQ_SO_DONE,LOOP_REQ_SO_DONE
     $ ,MP_LOOP_REQ_SO_DONE,CTCALL_REQ_SO_DONE,FILTER_SO

      INTEGER I_SO
      COMMON/I_SO/I_SO
      INTEGER I_LIB
      COMMON/I_LIB/I_LIB

      COMPLEX*16 AMP(NBORNAMPS)
      COMMON/AMPS/AMP
      COMPLEX*16 W(20,NWAVEFUNCS)
      COMMON/W/W

      COMPLEX*16 WL(MAXLWFSIZE,0:LOOPMAXCOEFS-1,MAXLWFSIZE,
     $ -1:NLOOPWAVEFUNCS)
      COMPLEX*16 PL(0:3,-1:NLOOPWAVEFUNCS)
      COMMON/WL/WL,PL

      COMPLEX*16 AMPL(3,NCTAMPS)
      COMMON/AMPL/AMPL

C     
C     ----------
C     BEGIN CODE
C     ----------

C     The target squared split order contribution is already reached
C      if true.
      IF (FILTER_SO.AND.LOOP_REQ_SO_DONE) THEN
        GOTO 1001
      ENDIF

C     Coefficient construction for loop diagram with ID 2
      CALL FFV1L1P0_3(PL(0,0),W(1,1),GC_5,ZERO,ZERO,PL(0,1),COEFS)
      CALL UPDATE_WL_0_0(WL(1,0,1,0),4,COEFS,4,4,WL(1,0,1,1))
      CALL FFV1L3_2(PL(0,1),W(1,2),GC_5,ZERO,ZERO,PL(0,2),COEFS)
      CALL UPDATE_WL_0_1(WL(1,0,1,1),4,COEFS,4,4,WL(1,0,1,2))
      CALL FFV2L1_2(PL(0,2),W(1,3),GC_47,ZERO,ZERO,PL(0,3),COEFS)
      CALL UPDATE_WL_1_1(WL(1,0,1,2),4,COEFS,4,4,WL(1,0,1,3))
      CALL CREATE_LOOP_COEFS(WL(1,0,1,3),2,4,1,1,1,2,H)
C     At this point, all loop coefficients needed for (QCD=2), i.e. of
C      split order ID=1, are computed.
      IF(FILTER_SO.AND.SQSO_TARGET.EQ.1) GOTO 4000

      GOTO 1001
 4000 CONTINUE
      LOOP_REQ_SO_DONE=.TRUE.
 1001 CONTINUE
      END

