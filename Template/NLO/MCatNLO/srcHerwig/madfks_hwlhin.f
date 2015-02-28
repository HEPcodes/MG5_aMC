C----------------------------------------------------------------------
      SUBROUTINE UPEVNT
C----------------------------------------------------------------------
C  Reads MC@NLO input files and fills Les Houches event common HEPEUP
C  Event file is written by MadFKS
C  Mostly derived from read_lhef_event() in handling_lhe_events.f
C----------------------------------------------------------------------
      INCLUDE 'HERWIG65.INC'
C---Les Houches Event Common Block
      INTEGER MAXNUP
      PARAMETER (MAXNUP=500)
      INTEGER NUP,IDPRUP,IDUP,ISTUP,MOTHUP,ICOLUP
      DOUBLE PRECISION XWGTUP,SCALUP,AQEDUP,AQCDUP,PUP,VTIMUP,SPINUP
      COMMON/HEPEUP/NUP,IDPRUP,XWGTUP,SCALUP,AQEDUP,AQCDUP,
     &              IDUP(MAXNUP),ISTUP(MAXNUP),MOTHUP(2,MAXNUP),
     &              ICOLUP(2,MAXNUP),PUP(5,MAXNUP),VTIMUP(MAXNUP),
     &              SPINUP(MAXNUP)
      INTEGER ISORH_LHE,IFKS_LHE,JFKS_LHE,FKSFATHER_LHE,IPARTNER_LHE
      DOUBLE PRECISION SCALE1_LHE,SCALE2_LHE
      DOUBLE PRECISION WGTCENTRAL,WGTMUMIN,WGTMUMAX,WGTPDFMIN,WGTPDFMAX
      INTEGER MQQ
      COMMON/cMQQ/MQQ
      INTEGER IUNIT
      PARAMETER (IUNIT=61)
      CHARACTER*80 STRING
      CHARACTER*140 BUFF
      character*12 dummy12
      character*2 dummy2
      CHARACTER*9 CH1
      INTEGER I,J,II,NPS,NNG,idwgt
      character*140 buff_tlh
      common/cbuff_tlh/buff_tlh
c evwgt_lh is meant to be passed to stdhep
      DOUBLE PRECISION EVWGT_LH
      COMMON/CEVWGT_LH/EVWGT_LH
      include 'reweight0.inc'
      integer iww,max_weight
      parameter (max_weight=maxscales*maxscales+maxpdfs+1)
      double precision ww(max_weight)
      common/cww/ww
C
      IF (IERROR.NE.0) RETURN
c
      ISORH_LHE=0
c Find the start of the events
      do while (.true.)
         read(iunit,'(a)')string
         if(INDEX(STRING,'<event').ne.0) exit
      enddo
      read(iunit,*)NUP,IDPRUP,XWGTUP,SCALUP,AQEDUP,AQCDUP
C---Les Houches expects mean weight to be the cross section in pb
      EVWGT_LH=XWGTUP
      XWGTUP=XWGTUP*MQQ
      do i=1,nup
        read(iunit,*)IDUP(I),ISTUP(I),MOTHUP(1,I),MOTHUP(2,I),
     #                 ICOLUP(1,I),ICOLUP(2,I),
     #                 PUP(1,I),PUP(2,I),PUP(3,I),PUP(4,I),PUP(5,I),
     #                 VTIMUP(I),SPINUP(I)
c Avoids rounding problems for zero-mass particles
        if(pup(5,i).eq.0.d0.and.istup(i).eq.1)then
          pup(4,i)=pup(1,i)**2+pup(2,i)**2+pup(3,i)**2
          pup(4,i)=sqrt(pup(4,i))
        endif
      enddo
      iww=1
      ww(iww)=XWGTUP/MQQ
      read(iunit,'(a)')buff
      if(buff(1:1).eq.'#')then
        buff_tlh=buff
        read(buff,*)ch1,iSorH_lhe,ifks_lhe,jfks_lhe,
     #                    fksfather_lhe,ipartner_lhe,
     #                    scale1_lhe,scale2_lhe,
     #                    jwgtinfo,mexternal,iwgtnumpartn,
     #         wgtcentral,wgtmumin,wgtmumax,wgtpdfmin,wgtpdfmax
        if(jwgtinfo.ge.1.and.jwgtinfo.le.4)then
          read(iunit,'(a)')string
          read(iunit,401)wgtref,wgtqes2(2)
          read(iunit,402)wgtxbj(1,1),wgtxbj(2,1),
     #                   wgtxbj(1,2),wgtxbj(2,2),
     #                   wgtxbj(1,3),wgtxbj(2,3),
     #                   wgtxbj(1,4),wgtxbj(2,4)
          if(jwgtinfo.eq.1)then
            read(iunit,403)wgtmuR2(1),wgtmuF12(1),wgtmuF22(1),
     #                     wgtmuR2(2),wgtmuF12(2),wgtmuF22(2)
          elseif(jwgtinfo.eq.2)then
            ii=iSorH_lhe+1
            if(ii.eq.3)ii=1
            read(iunit,404)wgtmuR2(ii),wgtmuF12(ii),wgtmuF22(ii)
            do i=1,mexternal
              read(iunit,405)(wgtkinE(j,i,iSorH_lhe),j=0,3)
            enddo
          elseif(jwgtinfo.eq.3 .or. jwgtinfo.eq.4)then
            do i=1,mexternal
              read(iunit,405)(wgtkinE(j,i,1),j=0,3)
            enddo
            do i=1,mexternal
              read(iunit,405)(wgtkinE(j,i,2),j=0,3)
            enddo
          endif
          read(iunit,441)wgtwreal(1),wgtwreal(2),
     #                   wgtwreal(3),wgtwreal(4)
          read(iunit,441)wgtwdeg(3),wgtwdeg(4),
     #                   wgtwdegmuf(3),wgtwdegmuf(4)
          read(iunit,405)wgtwborn(2),wgtwns(2),
     #                    wgtwnsmuf(2),wgtwnsmur(2)
          do i=1,iwgtnumpartn
            read(iunit,442)wgtwmcxsecE(i),
     #                     wgtmcxbjE(1,i),wgtmcxbjE(2,i)
          enddo
          if(jwgtinfo.eq.4) read(iunit,'(1x,e14.8)') wgtbpower
          read(iunit,'(a)')string
        elseif(jwgtinfo.eq.8)then
          read(iunit,'(a)')string
          read(iunit,406)wgtref,wgtxsecmu(1,1),numscales,numPDFpairs
          do i=1,numscales
            read(iunit,404)(wgtxsecmu(i,j),j=1,numscales)
          enddo
          do i=1,numPDFpairs
            nps=2*i-1
            nng=2*i
            read(iunit,404)wgtxsecPDF(nps),wgtxsecPDF(nng)
          enddo
          read(iunit,'(a)')string
        elseif(jwgtinfo.eq.9)then
          if (numscales.eq.0 .and. numPDFpairs.eq.0) then
             write (*,*) 'event file not correct format'
             call HWWARN('UPEVNT',502)
          endif
          read(iunit,'(a)')string
          wgtref=XWGTUP/MQQ
          do i=1,numscales
             do j=1,numscales
                call read_rwgt_line(iunit,idwgt,wgtxsecmu(i,j))
                if (numscales.ne.3) then
                   write (*,*) 'ERROR #1 in UPEVNT:',numscales
                   stop
                endif
                if(idwgt.eq.1001.and.(i.ne.1.or.j.ne.1).or.
     &             idwgt.eq.1002.and.(i.ne.1.or.j.ne.2).or.
     &             idwgt.eq.1003.and.(i.ne.1.or.j.ne.3).or.
     &             idwgt.eq.1004.and.(i.ne.2.or.j.ne.1).or.
     &             idwgt.eq.1005.and.(i.ne.2.or.j.ne.2).or.
     &             idwgt.eq.1006.and.(i.ne.2.or.j.ne.3).or.
     &             idwgt.eq.1007.and.(i.ne.3.or.j.ne.1).or.
     &             idwgt.eq.1008.and.(i.ne.3.or.j.ne.2).or.
     &             idwgt.eq.1009.and.(i.ne.3.or.j.ne.3))then
                   write(*,*)'incorrect event wgt id',idwgt,i,j
                   stop
                endif
c 1 = central,
c 2 = (muR0,muF0),    3 = (muR0,muFup),     4 = (muR0,muFdown)
c 5 = (muRup,muF0),   6 = (muRup,muFup),    7 = (muRup,muFdown)
c 8 = (muRdown,muF0), 9 = (muRdown,muFup), 10 = (muRdown,muFdown)
                iww=iww+1
                ww(iww)=wgtxsecmu(i,j)
             enddo
          enddo
          do i=1,2*numPDFpairs
             call read_rwgt_line(iunit,idwgt,wgtxsecPDF(i))
             iww=iww+1
             ww(iww)=wgtxsecPDF(i)
          enddo
          if (numscales.eq.0) then
             wgtxsecmu(1,1)=wgtref
          endif
          read(iunit,'(a)')string
        else
          do while(index(string,'</event>').eq.0)
             read(iunit,'(a)')string
          enddo
          backspace(iunit)
        endif
        read(iunit,'(a)')string
      else
        string=buff(1:len_trim(buff))
        buff_tlh=' '
      endif
      if(INDEX(STRING,'</event>').eq.0)then
        CALL HWWARN('UPEVNT',501)
      endif
c Modify what follows to set scale of H or S events in a different way
c$$$      IF(ISORH_LHE.EQ.2)THEN
c$$$c H events
c$$$        IF(SCALE2_LHE.GT.0.D0)SCALUP=SCALE2_LHE
c$$$      ENDIF
 401  format(2(1x,e14.8))
 402  format(8(1x,e14.8))
 403  format(6(1x,e14.8))
 404  format(3(1x,e14.8))
 405  format(4(1x,e14.8))
 406  format(2(1x,e14.8),2(1x,i3))
 441  format(4(1x,e16.10))
 442  format(1x,e16.10,2(1x,e14.8))
c 503  format(1x,i2,1x,i6,4(1x,d14.8))
c 504  format(1x,i8,1x,i2,4(1x,i4),5(1x,d14.8),2(1x,d10.4))
      END


C----------------------------------------------------------------------
      SUBROUTINE UPINIT
C----------------------------------------------------------------------
C  Reads MC@NLO input headers and fills Les Houches run common HEPRUP
C  Event file is written by MadFKS
C----------------------------------------------------------------------
      INCLUDE 'HERWIG65.INC'
C--Les Houches Common Blocks
      INTEGER MAXPUP
      PARAMETER(MAXPUP=100)
      INTEGER IDBMUP,PDFGUP,PDFSUP,IDWTUP,NPRUP,LPRUP
      DOUBLE PRECISION EBMUP,XSECUP,XERRUP,XMAXUP
      COMMON /HEPRUP/ IDBMUP(2),EBMUP(2),PDFGUP(2),PDFSUP(2),
     &                IDWTUP,NPRUP,XSECUP(MAXPUP),XERRUP(MAXPUP),
     &                XMAXUP(MAXPUP),LPRUP(MAXPUP)
      INTEGER MAXNUP
      PARAMETER (MAXNUP=500)
      INTEGER NUP,IDPRUP,IDUP,ISTUP,MOTHUP,ICOLUP
      DOUBLE PRECISION XWGTUP,SCALUP,AQEDUP,AQCDUP,PUP,VTIMUP,SPINUP
      COMMON/HEPEUP/NUP,IDPRUP,XWGTUP,SCALUP,AQEDUP,AQCDUP,
     &              IDUP(MAXNUP),ISTUP(MAXNUP),MOTHUP(2,MAXNUP),
     &              ICOLUP(2,MAXNUP),PUP(5,MAXNUP),VTIMUP(MAXNUP),
     &              SPINUP(MAXNUP)
c Hard event file (to be entered in Herwig driver)
      CHARACTER*50 QQIN
      COMMON/VVJIN/QQIN
      CHARACTER*80 STRING
      include 'reweight0.inc'
      integer nwgt,max_weight
      common/cnwgt/nwgt
      parameter (max_weight=maxscales*maxscales+maxpdfs+1)
      character*15 weights_info(max_weight)
      common/cwgtsinfo/weights_info
      double precision xmuR,xmuF
      integer iPDF,i
C
      numscales=0
      numPDFpairs=0
      nwgt=1
      weights_info(nwgt)="central value  "
      IF (IERROR.NE.0) RETURN
C--SET UP INPUT FILES
      OPEN(UNIT=61,FILE=QQIN,STATUS='UNKNOWN')
C--Read (non compulsory) headers here if need be
      DO WHILE(.TRUE.)
         READ(61,'(a)')STRING
c --> see if we have the new format for the weights
         IF ( INDEX(STRING,"<weightgroup type='scale_variation'").ne.0
     $        .and.STRING(1:1).ne.'#') then
            DO WHILE (.TRUE.)
               READ(61,'(a)') STRING
               if (INDEX(STRING,"</weightgroup>").ne.0 .and.
     $              STRING(1:1).ne.'#') exit
               numscales=numscales+1
               read(string(index(string,"muR")+4:index(string,"muF")-1),*)xmuR
               read(string(index(string,"muF")+4:index(string,"</w")-1),*)xmuF
c 1 = central,
c 2 = (muR0,muF0),    3 = (muR0,muFup),     4 = (muR0,muFdown)
c 5 = (muRup,muF0),   6 = (muRup,muFup),    7 = (muRup,muFdown)
c 8 = (muRdown,muF0), 9 = (muRdown,muFup), 10 = (muRdown,muFdown)
               write(weights_info(numscales+1), 111)"muR=",xmuR,"muF=",xmuF
            ENDDO
            nwgt=nwgt+numscales
            numscales=nint(sqrt(dble(numscales)))
            if (numscales.ne.3) then
               write (*,*) 'ERROR #1 in UPINIT:',numscales
               stop
            endif
         ELSEIF( INDEX(STRING,"<weightgroup type='PDF_variation'").ne.0
     $           .and.STRING(1:1).ne.'#') then
            DO WHILE (.TRUE.)
               READ(61,'(a)') STRING
               if (INDEX(STRING,"</weightgroup>").ne.0 .and.
     $              STRING(1:1).ne.'#') exit
               numPDFpairs=numPDFpairs+1
               read(string(index(string,"pdf")+7:index(string,"</w")-1),*)iPDF
               write(weights_info(numscales**2+numPDFpairs+1),112)
     &              'PDF=',iPDF,'   '
            ENDDO
            nwgt=nwgt+numPDFpairs
            numPDFpairs=numPDFpairs/2
         ELSEIF ( INDEX(STRING,'</header>').ne.0 .and.
     &        STRING(1:1).ne.'#' ) then
            EXIT
         ENDIF
      ENDDO
c--Find the start of the <init> block
      DO WHILE(.TRUE.)
         READ(61,'(a)')STRING
         IF ( INDEX(STRING,'<init>').ne.0 .and.
     &        STRING(1:1).ne.'#' ) exit
      ENDDO
C--Read up to </init> in the event file
      read(61,*,err=998)IDBMUP(1),IDBMUP(2),EBMUP(1),EBMUP(2),
     #            PDFGUP(1),PDFGUP(2),PDFSUP(1),PDFSUP(2),
     #            IDWTUP,NPRUP
      do i=1,NPRUP
         read(61,*,err=998)XSECUP(i),XERRUP(i),XMAXUP(i),LPRUP(i)
      enddo
 111  format(a4,f3.1,x,a4,f3.1)
 112  format(a4,i8,a3)
      return
 998  CALL HWWARN('UPINIT',500)
 999  END


C----------------------------------------------------------------------
      SUBROUTINE HWURSC(NP,PP)
C  RESCALES A SET OF NP (<21) 3-MOMENTA PP(1-3,*) IN
C  THEIR CMF TO PUT PP ON MASS-SHELL AT MASSES PP(5,*) 
C----------------------------------------------------------------------
      IMPLICIT NONE
      INTEGER NP,IP,IT,NT
      DOUBLE PRECISION PP(5,*),P(5,20),P2(20),M2(20),SP(5),
     & TINY,FAC,ECM,DCM,EP,STEP,FRT,HWUSQR
      DATA TINY,NT/1D-9,20/
      IF (NP.GT.20) CALL HWWARN('HWURSC',300+NP)
C--COMPUTE CM MOMENTUM
      CALL HWVZRO(4,SP)
      DO IP=1,NP
         CALL HWVSUM(4,PP(1,IP),SP,SP)
      ENDDO
      CALL HWUMAS(SP)
C--BOOST TO CMF
      DO IP=1,NP
         CALL HWULOF(SP,PP(1,IP),P(1,IP))
         P2(IP)=P(1,IP)**2+P(2,IP)**2+P(3,IP)**2
         M2(IP)=P(5,IP)**2
      ENDDO
C--ITERATE RESCALING OF 3-MOMENTA
      FAC=1D0
      DO IT=1,NT
         ECM=0D0
         DCM=0D0
         DO IP=1,NP
            EP=HWUSQR(M2(IP)+FAC*P2(IP))
            IF (EP.GT.0D0) THEN
               ECM=ECM+EP
               DCM=DCM+P2(IP)/EP
            ENDIF
         ENDDO
         IF (DCM.EQ.0D0) CALL HWWARN('HWURSC',390)
         STEP=2D0*(ECM-SP(5))/DCM
         FAC=FAC-STEP
         IF (ABS(STEP).LT.TINY) GOTO 100
      ENDDO
C--FAILED TO CONVERGE
      CALL HWWARN('HWURSC',1)
C--CONVERGED: RESCALE 3-MOMENTA AND BOOST BACK 
 100  IF (FAC.LT.0D0) CALL HWWARN('HWURSC',391)
      FRT=SQRT(FAC)
      DO IP=1,NP
         CALL HWVSCA(3,FRT,P(1,IP),P(1,IP))
         P(4,IP)=SQRT(M2(IP)+FAC*P2(IP))
         CALL HWULOB(SP,P(1,IP),PP(1,IP))
      ENDDO
      END


      subroutine read_rwgt_line(unit,id,wgt)
c read a line in the <rwgt> tag. The syntax should be
c  <wgt id='1001'> 0.1234567e+01 </wgt>
c The id should be exactly 4 digits long.
      implicit none
      integer unit,id,wgt_start,id_start
      double precision wgt
      character*100 buff
      read (unit,'(a)') buff
c Use char() to make sure that the non-standard characters are compiler
c independent (char(62)=">", char(61)="=", char(39)="'")
      wgt_start=index(buff,CHAR(39)//CHAR(62))+2
      id_start=index(buff,'id'//CHAR(61)//CHAR(39))+4
      read (buff(id_start:100),'(i4)') id
      read (buff(wgt_start:100),*) wgt
      return
      end
