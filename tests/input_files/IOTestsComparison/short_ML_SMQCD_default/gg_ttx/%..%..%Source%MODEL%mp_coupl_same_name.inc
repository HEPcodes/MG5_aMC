ccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
c      written by the UFO converter
ccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc

      REAL*16 G
      COMMON/MP_STRONG/ G

      COMPLEX*32 GAL(2)
      COMMON/MP_WEAK/ GAL

      COMPLEX*32 MU_R
      COMMON/MP_RSCALE/ MU_R


      REAL*16 MDL_MB,MDL_MH,MDL_MTA,MDL_MT,MDL_MZ,MDL_MW

      COMMON/MP_MASSES/ MDL_MB,MDL_MH,MDL_MTA,MDL_MT,MDL_MZ,MDL_MW


      REAL*16 MDL_WZ,MDL_WH,MDL_WT,MDL_WW

      COMMON/MP_WIDTHS/ MDL_WZ,MDL_WH,MDL_WT,MDL_WW


      COMPLEX*32 GC_4,GC_5,GC_6,R2_3GQ,R2_3GG,R2_GQQ,R2_GGQ,R2_GGB
     $ ,R2_GGT,R2_GGG_1,R2_GGG_2,R2_QQQ,R2_QQT,UV_3GG_1EPS,UV_3GB_1EPS
     $ ,UV_GQQG_1EPS,UV_GQQB_1EPS,UV_TMASS_1EPS,UVWFCT_B_0_1EPS
     $ ,UVWFCT_G_1_1EPS,UV_3GB,UV_3GT,UV_GQQB,UV_GQQT,UV_TMASS
     $ ,UVWFCT_T_0,UVWFCT_G_1,UVWFCT_G_2

      COMMON/MP_COUPLINGS/ GC_4,GC_5,GC_6,R2_3GQ,R2_3GG,R2_GQQ,R2_GGQ
     $ ,R2_GGB,R2_GGT,R2_GGG_1,R2_GGG_2,R2_QQQ,R2_QQT,UV_3GG_1EPS
     $ ,UV_3GB_1EPS,UV_GQQG_1EPS,UV_GQQB_1EPS,UV_TMASS_1EPS
     $ ,UVWFCT_B_0_1EPS,UVWFCT_G_1_1EPS,UV_3GB,UV_3GT,UV_GQQB,UV_GQQT
     $ ,UV_TMASS,UVWFCT_T_0,UVWFCT_G_1,UVWFCT_G_2


