      subroutine setrun
c----------------------------------------------------------------------
c     Sets the run parameters reading them from the run_card.dat
c
c 1. PDF set
c 2. Collider parameters
c 3. cuts
c---------------------------------------------------------------------- 
      implicit none
c
c     parameters
c
      integer maxpara
      parameter (maxpara=1000)
c
c     local
c     
      integer npara
      character*20 param(maxpara),value(maxpara)
c
c     include
c
      include 'genps.inc'
      include 'PDF/pdf.inc'
      include 'run.inc'
      include 'alfas.inc'
      include 'MODEL/coupl.inc'

      double precision D
      common/to_dj/D
c
c     local
c
      character*20 ctemp
      integer k,i,l1,l2
      character*132 buff
C
C     input cuts
C
      include 'cuts.inc'
C
C     BEAM POLARIZATION
C
      REAL*8 POL(2)
      common/to_polarization/ POL
      data POL/1d0,1d0/
c
c     Les Houches init block (for the <init> info)
c
      integer maxpup
      parameter(maxpup=100)
      integer idbmup,pdfgup,pdfsup,idwtup,nprup,lprup
      double precision ebmup,xsecup,xerrup,xmaxup
      common /heprup/ idbmup(2),ebmup(2),pdfgup(2),pdfsup(2),
     &     idwtup,nprup,xsecup(maxpup),xerrup(maxpup),
     &     xmaxup(maxpup),lprup(maxpup)
c
      include 'nexternal.inc'
      include 'leshouche_info.inc'
c
c
c
      logical gridrun,gridpack
      integer          iseed
      common /to_seed/ iseed
      integer nevents

      character*7 event_norm
c
c----------
c     start
c----------
      include 'run_card.inc'
      
c MZ add the possibility to have shower_MC input lowercase
      call to_upper(shower_MC)




c*********************************************************************
c     Minimum pt's                                                   *
c*********************************************************************
      ptb     = 0d0
      pta     = 0d0
      misset  = 0d0
      ptonium = 0d0
      
c*********************************************************************
c     Maximum pt's                                                   *
c*********************************************************************
      ptjmax=1d5
      ptbmax=1d5
      ptamax=1d5
      ptlmax=1d5
      missetmax=1d5

c*********************************************************************
c     Maximum rapidity (absolute value)                              *
c*********************************************************************
      etab=1d2
      etaa=1d2
      etaonium=1d2
      etajmin=0d0
      etabmin=0d0
      etaamin=0d0
      etalmin=0d0

      ej=0d0
      eb=0d0
      ea=0d0
      el=0d0

c*********************************************************************
c     Maximum E's                                                    *
c*********************************************************************
      ejmax=1d5
      ebmax=1d5
      eamax=1d5
      elmax=1d5

c*********************************************************************
c     Minimum DeltaR distance                                        *
c*********************************************************************
      drjj=0d0
      drbb=0d0
      draa=0d0
      drbj=0d0
      draj=0d0
      drjl=0d0
      drab=0d0
      drbl=0d0
      dral=0d0

c*********************************************************************
c     Maximum DeltaR distance                                        *
c*********************************************************************
      drjjmax=1d2
      drbbmax=1d2
      drllmax=1d2
      draamax=1d2
      drbjmax=1d2
      drajmax=1d2
      drjlmax=1d2
      drabmax=1d2
      drblmax=1d2
      dralmax=1d2

c*********************************************************************
c     Minimum invariant mass for pairs                               *
c*********************************************************************
      mmjj=0d0
      mmbb=0d0
      mmaa=0d0
      mmll=0d0

c*********************************************************************
c     Maximum invariant mass for pairs                               *
c*********************************************************************
      mmjjmax=1d5
      mmbbmax=1d5
      mmaamax=1d5
      mmllmax=1d5

c*********************************************************************
c     Min Maxi invariant mass for all leptons                        *
c*********************************************************************
      mmnl=0d0
      mmnlmax=1d5

c*********************************************************************
c     Inclusive cuts                                                 *
c*********************************************************************
      xptj=0d0
      xptb=0d0
      xpta=0d0
      xptl=0d0
      xmtc=0d0

c*********************************************************************
c     WBF cuts                                                       *
c*********************************************************************
      xetamin=0d0
      deltaeta=0d0

c*********************************************************************
c     Jet measure cuts                                               *
c*********************************************************************
      xqcut=0d0
      d=1d0

c*********************************************************************
c Set min pt of one heavy particle                                   *
c*********************************************************************
        ptheavy=0d0

c*********************************************************************
c Check   the pt's of the jets sorted by pt                          *
c*********************************************************************
        ptj1min=0d0
        ptj1max=1d5
        ptj2min=0d0
        ptj2max=1d5
        ptj3min=0d0
        ptj3max=1d5
        ptj4min=0d0
        ptj4max=1d5
        cutuse=0d0

c*********************************************************************
c Check  Ht                                                          *
c*********************************************************************
        ht2min=0d0
        ht3min=0d0
        ht4min=0d0
        ht2max=1d5
        ht3max=1d5
        ht4max=1d5
        htjmin=0d0
        htjmax=1d5

c*********************************************************************
c     Random Number Seed                                             *
c*********************************************************************

        gridrun=.false.
        gridpack=.false.

c************************************************************************     
c     Renormalization and factorization scales                          *
c************************************************************************     
c

c For backward compatibility
      scale = muR_ref_fixed
      q2fact(1) = muF1_ref_fixed**2      ! fact scale**2 for pdf1
      q2fact(2) = muF2_ref_fixed**2      ! fact scale**2 for pdf2     
      scalefact=muR_over_ref
      ellissextonfact=QES_over_ref

c check that the event normalization input is reasoble
      if (event_norm(1:7).ne.'average' .and. event_norm(1:3).ne.'sum')
     $     then
         write (*,*) 'Do not understand the event_norm parameter'/
     &        /' in the run_card.dat. Possible options are'/
     &        /' "average" or "sum". Current input is: ',event_norm
         open(unit=26,file='../../error',status='unknown')
         write (26,*) 'Do not understand the event_norm parameter'/
     &        /' in the run_card.dat. Possible options are'/
     &        /' "average" or "sum". Current input is: ',event_norm
         
         stop 1
      endif

c !!! Default behavior changed (MH, Aug. 07) !!!
c If no pdf, read the param_card and use the value from there and
c order of alfas running = 2

      if(lpp(1).ne.0.or.lpp(2).ne.0) then
          write(*,*) 'A PDF is used, so alpha_s(MZ) is going to be modified'
          call setpara('param_card.dat')
          asmz=G**2/(16d0*atan(1d0))
          write(*,*) 'Old value of alpha_s from param_card: ',asmz
          call pdfwrap
          write(*,*) 'New value of alpha_s from PDF ',pdlabel,':',asmz
      else
          call setpara('param_card.dat',.true.)
          asmz=G**2/(16d0*atan(1d0))
          nloop=2
          pdlabel='none'
          write(*,*) 'No PDF is used, alpha_s(MZ) from param_card is used'
          write(*,*) 'Value of alpha_s from param_card: ',asmz
          write(*,*) 'The default order of alpha_s running is fixed to ',nloop
      endif
c !!! end of modification !!!

C       Fill common block for Les Houches init info
      do i=1,2
        if(lpp(i).eq.1.or.lpp(i).eq.2) then
          idbmup(i)=2212
        elseif(lpp(i).eq.-1.or.lpp(i).eq.-2) then
          idbmup(i)=-2212
        elseif(lpp(i).eq.3) then
          idbmup(i)=11
        elseif(lpp(i).eq.-3) then
          idbmup(i)=-11
        elseif(lpp(i).eq.0) then
          idbmup(i)=idup_d(1,i,1)
        else
          idbmup(i)=lpp(i)
        endif
        ebmup(i)=ebeam(i)
      enddo
      call get_pdfup(pdlabel,pdfgup,pdfsup,lhaid)

      return
 99   write(*,*) 'error in reading'
      return
      end

C-------------------------------------------------
C   GET_PDFUP
C   Convert MadEvent pdf name to LHAPDF number
C-------------------------------------------------

      subroutine get_pdfup(pdfin,pdfgup,pdfsup,lhaid)
      implicit none

      character*(*) pdfin
      integer mpdf
      integer npdfs,i,pdfgup(2),pdfsup(2),lhaid

      parameter (npdfs=13)
      character*7 pdflabs(npdfs)
      data pdflabs/
     $   'none',
     $   'mrs02nl',
     $   'mrs02nn',
     $   'cteq4_m',
     $   'cteq4_l',
     $   'cteq4_d',
     $   'cteq5_m',
     $   'cteq5_d',
     $   'cteq5_l',
     $   'cteq5m1',
     $   'cteq6_m',
     $   'cteq6_l',
     $   'cteq6l1'/
      integer numspdf(npdfs)
      data numspdf/
     $   00000,
     $   20250,
     $   20270,
     $   19150,
     $   19170,
     $   19160,
     $   19050,
     $   19060,
     $   19070,
     $   19051,
     $   10000,
     $   10041,
     $   10042/


      if(pdfin.eq."lhapdf") then
        write(*,*)'using LHAPDF'
        do i=1,2
           pdfgup(i)=-1
           pdfsup(i)=lhaid
        enddo
        return
      endif

      
      mpdf=-1
      do i=1,npdfs
        if(pdfin(1:len_trim(pdfin)) .eq. pdflabs(i))then
          mpdf=numspdf(i)
        endif
      enddo

      if(mpdf.eq.-1) then
        write(*,*)'ERROR: pdf ',pdfin,' not implemented in get_pdfup.'
        write(*,*)'known pdfs are'
        write(*,*) pdflabs
        open(unit=26,file='../../error',status='unknown')
        write(26,*)'ERROR: pdf ',pdfin,' not implemented in get_pdfup.'
        write(26,*)'known pdfs are'
        write(26,*) pdflabs
        stop 1
c$$$        write(*,*)'using ',pdflabs(12)
c$$$        mpdf=numspdf(12)
      endif

      do i=1,2
        pdfgup(i)=-1
        pdfsup(i)=mpdf
      enddo

      return
      end
