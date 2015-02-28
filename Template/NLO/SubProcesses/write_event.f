      subroutine finalize_event(xx,weight,lunlhe,plotEv,putonshell)
      implicit none
      include 'nexternal.inc'
      include "genps.inc"
      integer ndim,ipole
      common/tosigint/ndim,ipole
      integer           iconfig
      common/to_configs/iconfig
      integer itmax,ncall
      common/citmax/itmax,ncall
      logical Hevents
      common/SHevents/Hevents
      integer i,j,lunlhe
      include 'mint.inc'
      real*8 xx(ndimmax),weight,plot_wgt,evnt_wgt
      logical plotEv, putonshell
      double precision wgt,unwgtfun
      double precision x(99),p(0:3,nexternal)
      integer jpart(7,-nexternal+3:2*nexternal-3)
      double precision pb(0:4,-nexternal+3:2*nexternal-3)
      logical unwgt
      double precision evtsgn
      common /c_unwgt/evtsgn,unwgt
      integer iplot_ev,iplot_cnt,iplot_born
      parameter (iplot_ev=11)
      parameter (iplot_cnt=12)
      parameter (iplot_born=20)
      double precision ybst_til_tolab,ybst_til_tocm,sqrtshat,shat
      common/parton_cms_stuff/ybst_til_tolab,ybst_til_tocm,
     #                        sqrtshat,shat
      double precision p1_cnt(0:3,nexternal,-2:2)
      double precision wgt_cnt(-2:2)
      double precision pswgt_cnt(-2:2)
      double precision jac_cnt(-2:2)
      common/counterevnts/p1_cnt,wgt_cnt,pswgt_cnt,jac_cnt

      integer np,npart
      double precision jampsum,sumborn,shower_scale
      double complex wgt1(2)
      character*4 abrv
      common /to_abrv/ abrv
      double precision p_born(0:3,nexternal-1)
      common/pborn/p_born

      do i=1,99
        if(i.le.ndim)then
          x(i)=xx(i)
        else
          x(i)=-9d99
        endif
      enddo
      
      wgt=1d0
c Normalization to the number of requested events is done in subroutine
c topout (madfks_plot.f), so multiply here to get # of events.
      evnt_wgt=evtsgn*weight
      plot_wgt=evnt_wgt*itmax*ncall
      call generate_momenta(ndim,iconfig,wgt,x,p)
c
c Get all the info we need for writing the events.
c      
      if (Hevents) then
         call set_cms_stuff(-100)
      else
         call set_cms_stuff(0)
      endif

      call add_write_info(p_born,p,ybst_til_tolab,iconfig,Hevents,
     &     putonshell,ndim,ipole,x,jpart,npart,pb,shower_scale)

c Plot the events also on the fly
      if(plotEv) then
         if (Hevents) then
            call outfun(p,ybst_til_tolab,plot_wgt,iplot_ev)
         else
            call outfun(p1_cnt(0,1,0),ybst_til_tolab,plot_wgt,iplot_cnt)
         endif
      endif

      call unweight_function(p_born,unwgtfun)
      if (unwgtfun.ne.0d0) then
         evnt_wgt=evnt_wgt/unwgtfun
      else
         write (*,*) 'ERROR in finalize_event, unwgtfun=0',unwgtfun
         stop
      endif

      if (abrv.ne.'grid') then
c  Write-out the events
         call write_events_lhe(pb(0,1),evnt_wgt,jpart(1,1),npart,lunlhe
     &        ,shower_scale)
      else
         call write_random_numbers(lunlhe)
      endif
      
      return
      end

      subroutine write_header_init
      implicit none
      integer lunlhe,nevents
      double precision res,err,res_abs
      character*120 string
      logical Hevents
      common/SHevents/Hevents
      character*10 MonteCarlo
c
      common/cMonteCarloType/MonteCarlo
      integer ifile,ievents
      double precision inter,absint,uncer
      common /to_write_header_init/inter,absint,uncer,ifile,ievents

c Les Houches init block (for the <init> info)
      integer maxpup
      parameter(maxpup=100)
      integer idbmup,pdfgup,pdfsup,idwtup,nprup,lprup
      double precision ebmup,xsecup,xerrup,xmaxup
      common /heprup/ idbmup(2),ebmup(2),pdfgup(2),pdfsup(2),
     &     idwtup,nprup,xsecup(maxpup),xerrup(maxpup),
     &     xmaxup(maxpup),lprup(maxpup)
c Scales
      character*80 muR_id_str,muF1_id_str,muF2_id_str,QES_id_str
      common/cscales_id_string/muR_id_str,muF1_id_str,
     #                         muF2_id_str,QES_id_str


c      open(unit=58,file='res_1',status='old')
c      read(58,'(a)')string
c      read(string(index(string,':')+1:index(string,'+/-')-1),*) res_abs
c      close(58)
      lunlhe=ifile
c get info on beam and PDFs
      call setrun
      XSECUP(1)=inter
      XERRUP(1)=uncer
      XMAXUP(1)=absint/ievents
      LPRUP(1)=66
      IDWTUP=-4
      NPRUP=1

      write(lunlhe,'(a)')'<LesHouchesEvents version="1.0">'
      write(lunlhe,'(a)')'  <!--'
      write(lunlhe,'(a)')'  <scalesfunctionalform>'
      write(lunlhe,'(2a)')'    muR  ',muR_id_str(1:len_trim(muR_id_str))
      write(lunlhe,'(2a)')'    muF1 ',muF1_id_str(1:len_trim(muF1_id_str))
      write(lunlhe,'(2a)')'    muF2 ',muF2_id_str(1:len_trim(muF2_id_str))
      write(lunlhe,'(2a)')'    QES  ',QES_id_str(1:len_trim(QES_id_str))
      write(lunlhe,'(a)')'  </scalesfunctionalform>'
      write(lunlhe,'(a)')MonteCarlo
      write(lunlhe,'(a)')'  -->'
      write(lunlhe,'(a)')'  <header>'
      write(lunlhe,250)ievents
      write(lunlhe,'(a)')'  </header>'
      write(lunlhe,'(a)')'  <init>'
      write(lunlhe,501)IDBMUP(1),IDBMUP(2),EBMUP(1),EBMUP(2),
     #                PDFGUP(1),PDFGUP(2),PDFSUP(1),PDFSUP(2),
     #                IDWTUP,NPRUP
      write(lunlhe,502)XSECUP(1),XERRUP(1),XMAXUP(1),LPRUP(1)
      write(lunlhe,'(a)')'  </init>'
 250  format(1x,i8)
 501  format(2(1x,i6),2(1x,d14.8),2(1x,i2),2(1x,i6),1x,i2,1x,i3)
 502  format(3(1x,d14.8),1x,i6)

      return
      end

      subroutine write_events_lhe(p,wgt,ic,npart,lunlhe,shower_scale)
      implicit none
      include "nexternal.inc"
      include "coupl.inc"
      include "madfks_mcatnlo.inc"
      include 'reweight.inc'
      double precision p(0:4,2*nexternal-3),wgt
      integer ic(7,2*nexternal-3),npart,lunlhe
      double precision pi,zero
      parameter (pi=3.1415926535897932385d0)
      parameter (zero=0.d0)
      integer ievent,izero
      parameter (izero=0)
      double precision aqcd,aqed,scale
      character*140 buff
      double precision shower_scale
      INTEGER MAXNUP,i
      PARAMETER (MAXNUP=500)
      INTEGER NUP,IDPRUP,IDUP(MAXNUP),ISTUP(MAXNUP),
     # MOTHUP(2,MAXNUP),ICOLUP(2,MAXNUP)
      DOUBLE PRECISION XWGTUP,AQEDUP,AQCDUP,
     # PUP(5,MAXNUP),VTIMUP(MAXNUP),SPINUP(MAXNUP)
      include 'nFKSconfigs.inc'
      INTEGER NFKSPROCESS
      COMMON/C_NFKSPROCESS/NFKSPROCESS
      integer iSorH_lhe,ifks_lhe(fks_configs) ,jfks_lhe(fks_configs)
     &     ,fksfather_lhe(fks_configs) ,ipartner_lhe(fks_configs)
      double precision scale1_lhe(fks_configs),scale2_lhe(fks_configs)
      common/cto_LHE1/iSorH_lhe,ifks_lhe,jfks_lhe,
     #                fksfather_lhe,ipartner_lhe
      common/cto_LHE2/scale1_lhe,scale2_lhe
      logical firsttime
      data firsttime/.true./
c
      if (firsttime) then
         call write_header_init
         firsttime=.false.
      endif
      ievent=66
      scale = shower_scale
      aqcd=g**2/(4d0*pi)
      aqed=gal(1)**2/(4d0*pi)

      if(AddInfoLHE)then
        if(.not.doreweight)then
           write(buff,201)'#aMCatNLO',iSorH_lhe,ifks_lhe(nFKSprocess)
     &          ,jfks_lhe(nFKSprocess),fksfather_lhe(nFKSprocess)
     &          ,ipartner_lhe(nFKSprocess),scale1_lhe(nFKSprocess)
     &          ,scale2_lhe(nFKSprocess),izero,izero,izero,zero,zero
     &          ,zero,zero,zero
        else
          if(iwgtinfo.lt.1.or.iwgtinfo.gt.5)then
            write(*,*)'Error in write_events_lhe'
            write(*,*)'  Inconsistency in reweight parameters'
            write(*,*)doreweight,iwgtinfo
            stop
          endif
          write(buff,201)'#aMCatNLO',iSorH_lhe,ifks_lhe(nFKSprocess)
     &         ,jfks_lhe(nFKSprocess),fksfather_lhe(nFKSprocess)
     &         ,ipartner_lhe(nFKSprocess),scale1_lhe(nFKSprocess)
     &         ,scale2_lhe(nFKSprocess),iwgtinfo,nexternal,iwgtnumpartn
     &         ,zero,zero,zero,zero,zero
        endif
      else
        buff=' '
      endif

c********************************************************************
c     Writes one event from data file #lun according to LesHouches
c     ic(1,*) = Particle ID
c     ic(2.*) = Mothup(1)
c     ic(3,*) = Mothup(2)
c     ic(4,*) = ICOLUP(1)
c     ic(5,*) = ICOLUP(2)
c     ic(6,*) = ISTUP   -1=initial state +1=final  +2=decayed
c     ic(7,*) = Helicity
c********************************************************************

      NUP=npart
      IDPRUP=ievent
      XWGTUP=wgt
      AQEDUP=aqed
      AQCDUP=aqcd
      do i=1,NUP
        IDUP(i)=ic(1,i)
        ISTUP(i)=ic(6,i)
        MOTHUP(1,i)=ic(2,i)
        MOTHUP(2,i)=ic(3,i)
        ICOLUP(1,i)=ic(4,i)
        ICOLUP(2,i)=ic(5,i)
        PUP(1,i)=p(1,i)
        PUP(2,i)=p(2,i)
        PUP(3,i)=p(3,i)
        PUP(4,i)=p(0,i)
        PUP(5,i)=p(4,i)
        VTIMUP(i)=0.d0
        SPINUP(i)=dfloat(ic(7,i))
      enddo
      call write_lhef_event(lunlhe,
     #    NUP,IDPRUP,XWGTUP,scale,AQEDUP,AQCDUP,
     #    IDUP,ISTUP,MOTHUP,ICOLUP,PUP,VTIMUP,SPINUP,buff)

 201  format(a9,1x,i1,4(1x,i2),2(1x,d14.8),1x,i1,2(1x,i2),5(1x,d14.8))
      return
      end

      subroutine write_random_numbers(lunlhe)
      implicit none
      integer lunlhe,i
      double precision x(99),sigintF_save,f_abs_save
      common /c_sigint/ x,sigintF_save,f_abs_save
      integer ndim,ipole
      common/tosigint/ndim,ipole
      write (lunlhe,'(a)')'  <event>'
      write (lunlhe,*) ndim,sigintF_save,f_abs_save
      write (lunlhe,*) (x(i),i=1,ndim)
      write (lunlhe,'(a)')'  </event>'
      return
      end
