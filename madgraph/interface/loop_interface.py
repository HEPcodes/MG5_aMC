################################################################################
#
# Copyright (c) 2009 The MadGraph5_aMC@NLO Development team and Contributors
#
# This file is a part of the MadGraph5_aMC@NLO project, an application which 
# automatically generates Feynman diagrams and matrix elements for arbitrary
# high-energy processes in the Standard Model and beyond.
#
# It is subject to the MadGraph5_aMC@NLO license which should accompany this 
# distribution.
#
# For more information, visit madgraph.phys.ucl.ac.be and amcatnlo.web.cern.ch
#
################################################################################
"""A user friendly command line interface to access all MadGraph5_aMC@NLO features.
   Uses the cmd package for command interpretation and tab completion.
"""

import os
import shutil
import time
import logging

import madgraph
from madgraph import MG4DIR, MG5DIR, MadGraph5Error
import madgraph.interface.madgraph_interface as mg_interface
import madgraph.core.base_objects as base_objects
import madgraph.core.diagram_generation as diagram_generation
import madgraph.loop.loop_diagram_generation as loop_diagram_generation
import madgraph.loop.loop_base_objects as loop_base_objects
import madgraph.loop.loop_helas_objects as loop_helas_objects
import madgraph.core.helas_objects as helas_objects
import madgraph.iolibs.export_v4 as export_v4
import madgraph.iolibs.helas_call_writers as helas_call_writers
import madgraph.iolibs.file_writers as writers
import madgraph.interface.launch_ext_program as launch_ext
import aloha

# Special logger for the Cmd Interface
logger = logging.getLogger('cmdprint')

#useful shortcut
pjoin = os.path.join

class CheckLoop(mg_interface.CheckValidForCmd):

    def check_display(self, args):
        """ Check the arguments of the display diagrams command in the context
        of the Loop interface."""
        
        mg_interface.MadGraphCmd.check_display(self,args)
        
        if all([not amp['process']['has_born'] for amp in self._curr_amps]):
            if args[0]=='diagrams' and len(args)>=2 and args[1]=='born':
                raise self.InvalidCmd("Processes generated do not have born diagrams.")
        
        if args[0]=='diagrams' and len(args)>=3 and args[1] not in ['born','loop']:
            raise self.InvalidCmd("Can only display born or loop diagrams, not %s."%args[1])

    def check_tutorial(self, args):
        """check the validity of the line"""
        if len(args) == 0:
            #this means mg5 tutorial
            args.append('MadLoop')
        else:
            return mg_interface.CheckValidForCmd.check_tutorial(self,args)

    def check_output(self, args):
        """ Check the arguments of the output command in the context
        of the Loop interface."""
        
        mg_interface.MadGraphCmd.check_output(self,args)
        
        if args and args[0] in ['standalone']:
            self._export_format = args.pop(0)
        else:
            self._export_format = 'standalone'

    def check_launch(self, args, options):
        """ Further check that only valid options are given to the MadLoop
        default launcher."""
        
        mg_interface.MadGraphCmd.check_launch(self,args,options)
        if int(options.cluster) != 0 :
            return self.InvalidCmd, 'MadLoop standalone runs cannot be '+\
                                    'performed on a cluster.'
        
        if int(options.multicore) != 0 :
            logger.warning('MadLoop standalone can only run on a single core,'+\
                                                ' so the -m option is ignored.')
            options.multicore = '0'
        
        if options.laststep != '' :
            logger.warning('The -laststep option is only used for Madevent.'+\
                           'Ignoring this option')
            options.multicore = ''
        
        if options.interactive :
            logger.warning('No interactive mode for MadLoop standalone runs.')
            options.interactive = False

class CheckLoopWeb(mg_interface.CheckValidForCmdWeb, CheckLoop):
    pass

class CompleteLoop(mg_interface.CompleteForCmd):
    
    def complete_display(self, text, line, begidx, endidx):
        "Complete the display command in the context of the Loop interface"

        args = self.split_arg(line[0:begidx])

        if len(args) == 2 and args[1] == 'diagrams':
            return self.list_completion(text, ['born', 'loop'])
        else:
            return mg_interface.MadGraphCmd.complete_display(self, text, line,
                                                                 begidx, endidx)

class HelpLoop(mg_interface.HelpToCmd):

    def help_display(self):   
        mg_interface.MadGraphCmd.help_display(self)
        logger.info("   In ML5, after display diagrams, the user can add the option")
        logger.info("   \"born\" or \"loop\" to display only the corresponding diagrams.")


class CommonLoopInterface(mg_interface.MadGraphCmd):
    """ An additional layer between MadGraphInterface and LoopInterface as well
    as aMCatNLO interface, to put the common feature of these two here."""

    def rate_proc_difficulty(self, proc, mode):
        """ Gives an integer more or less representing the difficulty of the process.
        For now it is very basic and such that "difficult" processes start at 
        a value of about 35."""
        
        def pdg_difficulty(pdg):
            """ Gives a score from the pdg of a leg to state how it increases the
            difficulty of the process """
            # For now, it is only based on the color charge. One can change that
            # of course.
            part=self._curr_model.get_particle(pdg)
            if abs(part.get_color())==1:
                return 2
            elif abs(part.get_color())==3:
                return 3
            elif abs(part.get_color())==6:
                return 4
            elif abs(part.get_color())==8:
                return 6

        score = 0
        for leg in proc.get('legs'):
            if isinstance(leg,base_objects.MultiLeg):
                score += max([pdg_difficulty(id) for id in leg['ids']])
                # add one if it has more than one particle
                if len(leg['ids'])>1:
                    score += 1
            else:
                score += pdg_difficulty(leg.get('id'))
        
        # No integration planned right away if only virtual, remove 6
        if proc['NLO_mode']=='virt':
            score = score - 6
        # Only reals, then again remove 6
        if proc['NLO_mode']=='real':
            score = score - 6
        # If tree only then it is easy
        if proc['NLO_mode']=='tree':
            return 0
        return score

    def do_set(self, line, log=True):
        """Set the loop optimized output while correctly switching to the
        Feynman gauge if necessary.
        """

        mg_interface.MadGraphCmd.do_set(self,line,log)
        
        args = self.split_arg(line)
        self.check_set(args)

        if args[0] == 'gauge' and args[1] == 'unitary' and \
            not self.options['gauge']=='unitary' and \
            isinstance(self._curr_model,loop_base_objects.LoopModel) and \
                 not self._curr_model['perturbation_couplings'] in [[],['QCD']]:
            if log: logger.warning('You will only be able to do tree level and QCD'+\
                                           ' corrections in the unitary gauge.')

    def proc_validity(self, proc, mode):
        """ Check that the process or processDefinition describes a process that 
        ML5 can handle. Mode specifies who called the function,
        typically ML5, ML5_check or aMCatNLO. This allows to relieve some limitation
        depending on the functionality."""

        tool = 'MadLoop' if mode.startswith('ML5') else 'aMC@NLO'
        # The threshold for the triggering of the 'Warning difficult process'
        # message.
        difficulty_threshold = 100
        # Check that we have something    
        if not proc:
            raise self.InvalidCmd("Empty or wrong format process, please try again.")
        
        # Check that we have the same number of initial states as
        # existing processes
        if self._curr_amps and self._curr_amps[0].get_ninitial() != \
            proc.get_ninitial():
            raise self.InvalidCmd("Can not mix processes with different number of initial states.")               
            
        if proc.get_ninitial()==1:
            raise self.InvalidCmd("At this stage %s cannot handle decay process."%tool+\
                                  "\nIt is however a straight-forward extension which "+\
                                  "will come out with the next release.")                           

        if isinstance(proc, base_objects.ProcessDefinition) and mode.startswith('ML5'):
            if proc.has_multiparticle_label():
                raise self.InvalidCmd(
                  "When running ML5 standalone, multiparticle labels cannot be"+\
                  " employed. Please use the FKS5 interface instead.")
        
        if proc['decay_chains']:
            raise self.InvalidCmd(
                  "ML5 cannot yet decay a core process including loop corrections.")
        
        if proc.are_decays_perturbed():
            raise self.InvalidCmd(
                  "The processes defining the decay of the core process cannot"+\
                  " include loop corrections.")
        
        if not proc['perturbation_couplings'] and mode.startswith('ML5'):
            raise self.InvalidCmd(
                "Please perform tree-level generations within default MG5 interface.")
        if not 'real':
            if not isinstance(self._curr_model,loop_base_objects.LoopModel) or \
                                             not proc['perturbation_couplings']:
                raise self.InvalidCmd(
                "The current model does not allow for loop computations.")
        
            miss_order = [ p_order for p_order in proc['perturbation_couplings'] \
                if p_order not in self._curr_model.get('perturbation_couplings')]
            if len(miss_order)>0 and not 'real' in mode:
                raise self.InvalidCmd(
                    "Perturbation orders %s not among"%str(miss_order) + \
                    " the perturbation orders allowed for by the loop model.")
                
            if proc['perturbation_couplings'] not in [[],['QCD']]:
                raise self.InvalidCmd(
                    "The process perturbation coupling orders %s are beyond "+\
                    "tree level or only QCD corrections. MadLoop can only work"+\
                    " in the Feynman gauge for these. Please set the gauge to "+\
                                                      " Feynman and try again.")
                
        proc_diff = self.rate_proc_difficulty(proc, mode)
        logger.debug('Process difficulty estimation: %d'%proc_diff)
        if proc_diff >= difficulty_threshold:
            msg = """
  The %s you attempt to generate appears to be of challenging difficulty, but it will be tried anyway. If you have successfully studied it with MadGraph5_aMC@NLO, please report it.
"""
            logger.warning(msg%proc.nice_string().replace('Process:','process'))

    def validate_model(self, loop_type='virtual', stop=True):
        """ Upgrade the model sm to loop_sm if needed """

        if not self._curr_model:
            mg_interface.MadGraphCmd.do_set(self,'gauge Feynman')
            #import model with correct treatment of the history
            return

        if not isinstance(self._curr_model,loop_base_objects.LoopModel) or \
           self._curr_model['perturbation_couplings']==[]:
            if loop_type.startswith('real'):
                if loop_type == 'real':
                    logger.info(\
                      "Beware that real corrections are generated from a tree-level model.")
                if loop_type == 'real_init' and \
                               self._curr_model.get('name').split('-')[0]!='sm':
                    logger.info(\
                      "You are entering aMC@NLO with a model which does not "+\
                                                   " support loop corrections.")
            else:
                model_path = self._curr_model.get('modelpath')
                model_name = self._curr_model.get('name')
                if model_name.split('-')[0]=='sm':
                    # Once the loop_sm model will support Feynman gauge, please
                    # uncomment below.
#                    if self.options['gauge']!='Feynman':
#                        self._curr_model = None
#                        mg_interface.MadGraphCmd.do_set(self,'gauge Feynman')
                    logger.info(\
                      "The default sm model does not allow to generate"+
                      " loop processes. MG5_aMC now loads 'loop_sm' instead.")
                    #import model with correct treatment of the history
                    self.history.move_to_last('generate')
                    last_command = self.history[-1]
                    self.exec_cmd(" import model loop_%s" % model_name, precmd=True)
                    self.history.append(last_command)
                    
                elif stop:
                    raise self.InvalidCmd(
                      "The model %s cannot handle loop processes"%model_name)    
                    
        if loop_type and not loop_type.startswith('real') and \
                 not self.options['gauge']=='Feynman' and \
                 not self._curr_model['perturbation_couplings'] in [[],['QCD']]:
            if 1 in self._curr_model.get('gauge'):
                logger.info("Setting gauge to Feynman in order to process all"+\
                           " possible loop computations available in the model")
                mg_interface.MadGraphCmd.do_set(self,'gauge Feynman')
            else:
                logger.warning("You will only be able to do tree level and QCD"+\
      " corrections with this model because it does not support Feynman gauge.")

class LoopInterface(CheckLoop, CompleteLoop, HelpLoop, CommonLoopInterface):
        
    def __init__(self, mgme_dir = '', *completekey, **stdin):
        """ Special init tasks for the Loop Interface """

        mg_interface.MadGraphCmd.__init__(self, mgme_dir = '', *completekey, **stdin)
        self.setup()
    
    def setup(self):
        """ Special tasks when switching to this interface """

        # Refresh all the interface stored value as things like generated
        # processes and amplitudes are not to be reused in between different
        # interfaces
        # Clear history, amplitudes and matrix elements when a model is imported
        # Remove previous imports, generations and outputs from history
        self.history.clean(remove_bef_last='import',
                           to_keep=['set','load','import', 'define'])
        # Reset amplitudes and matrix elements
        self._done_export=False
        self._curr_amps = diagram_generation.AmplitudeList()
        self._curr_matrix_elements = helas_objects.HelasMultiProcess()
        self._v4_export_formats = []
        self._export_formats = [ 'matrix', 'standalone' ]
        self._nlo_modes_for_completion = ['virt']
        self.validate_model()
        # Set where to look for CutTools installation.
        # In further versions, it will be set in the same manner as _mgme_dir so that
        # the user can chose its own CutTools distribution.
        self._cuttools_dir=str(os.path.join(self._mgme_dir,'vendor','CutTools'))
        if not os.path.isdir(os.path.join(self._cuttools_dir, 'src','cts')):
            logger.warning(('Warning: Directory %s is not a valid CutTools directory.'+\
                           'Using default CutTools instead.') % \
                             self._cuttools_dir)
            self._cuttools_dir=str(os.path.join(self._mgme_dir,'vendor','CutTools'))
    
    def do_display(self,line, *argss, **opt):
        """ Display born or loop diagrams, otherwise refer to the default display
        command """
        
        args = self.split_arg(line)
        #check the validity of the arguments
        self.check_display(args)
        
        if args[0]=='diagrams':
            if len(args)>=2 and args[1] in ['loop','born']:
                self.draw(' '.join(args[2:]),args[1])
            else:
                self.draw(' '.join(args[1:]),'all')
        else:
            mg_interface.MadGraphCmd.do_display(self,line,*argss,**opt)

    def do_output(self, line):
        """Main commands:Initialize a new Template or reinitialize one"""
        
        args = self.split_arg(line)
        # Check Argument validity
        self.check_output(args)
        
        noclean = '-noclean' in args
        force = '-f' in args 
        nojpeg = '-nojpeg' in args
        main_file_name = ""
        try:
            main_file_name = args[args.index('-name') + 1]
        except Exception:
            pass

        # Whatever the format we always output the quadruple precision routines
        # to allow for curing possible unstable points.
        aloha_original_quad_mode = aloha.mp_precision
        aloha.mp_precision = True

        if self._export_format not in ['standalone']:
            raise self.InvalidCmd('ML5 only support standalone as export format.')

        if not os.path.isdir(self._export_dir) and \
           self._export_format in ['matrix']:
            raise self.InvalidCmd('Specified export directory %s does not exist.'\
                                                         %str(self._export_dir))

        if not force and not noclean and os.path.isdir(self._export_dir)\
               and self._export_format in ['standalone']:
            # Don't ask if user already specified force or noclean
            logger.info('INFO: directory %s already exists.' % self._export_dir)
            logger.info('If you continue this directory will be cleaned')
            answer = self.ask('Do you want to continue?', 'y', ['y','n'])
            if answer != 'y':
                raise self.InvalidCmd('Stopped by user request')
            else:
                try:
                    shutil.rmtree(self._export_dir)
                except OSError:
                    raise self.InvalidCmd('Could not remove directory %s.'\
                                                         %str(self._export_dir))     

        if not self._curr_amps[0].get('process').get('has_born') and \
                                          self.options['loop_optimized_output']:
            logger.warning('The loop optimized output is not available for '+\
                     'loop-induced processes. Now setting this option to False.')
            self.do_set('loop_optimized_output False')

        self._curr_exporter = export_v4.ExportV4Factory(self, \
                                                 noclean, output_type='madloop')

        if self._export_format in ['standalone']:
            self._curr_exporter.copy_v4template(modelname=self._curr_model.get('name'))

        # Reset _done_export, since we have new directory
        self._done_export = False

        # Perform export and finalize right away
        self.ML5export(nojpeg, main_file_name)

        # Automatically run finalize
        self.ML5finalize(nojpeg)
            
        # Remember that we have done export
        self._done_export = (self._export_dir, self._export_format)

        # Reset _export_dir, so we don't overwrite by mistake later
        self._export_dir = None

        # Put aloha back in its original mode.
        aloha.mp_precision = aloha_original_quad_mode

    # Export a matrix element
    
    def ML5export(self, nojpeg = False, main_file_name = ""):
        """Export a generated amplitude to file"""

        def generate_matrix_elements(self):
            """Helper function to generate the matrix elements before exporting"""

            # Sort amplitudes according to number of diagrams,
            # to get most efficient multichannel output
            self._curr_amps.sort(lambda a1, a2: a2.get_number_of_diagrams() - \
                                 a1.get_number_of_diagrams())

            cpu_time1 = time.time()
            ndiags = 0
            if not self._curr_matrix_elements.get_matrix_elements():
                self._curr_matrix_elements = \
                    loop_helas_objects.LoopHelasProcess(self._curr_amps,
                    optimized_output = self.options['loop_optimized_output'])
                ndiags = sum([len(me.get('diagrams')) for \
                              me in self._curr_matrix_elements.\
                              get_matrix_elements()])
                # assign a unique id number to all process
                uid = 0 
                for me in self._curr_matrix_elements.get_matrix_elements():
                    uid += 1 # update the identification number
                    me.get('processes')[0].set('uid', uid)

            cpu_time2 = time.time()
            return ndiags, cpu_time2 - cpu_time1

        # Start of the actual routine
        ndiags, cpu_time = generate_matrix_elements(self)

        calls = 0

        path = self._export_dir
        if self._export_format in ['standalone']:
            path = pjoin(path, 'SubProcesses')
            
        cpu_time1 = time.time()

        # Pick out the matrix elements in a list
        matrix_elements = \
                        self._curr_matrix_elements.get_matrix_elements()

        # Fortran MadGraph5_aMC@NLO Standalone
        if self._export_format == 'standalone':
            for me in matrix_elements:
                calls = calls + \
                        self._curr_exporter.generate_subprocess_directory_v4(\
                            me, self._curr_fortran_model)
            # If all ME's do not share the same maximum loop vertex rank and the
            # same loop maximum wavefunction size, we need to set the maximum
            # in coef_specs.inc of the HELAS Source and warn the user that this
            # might be a problem
            if self.options['loop_optimized_output'] and len(matrix_elements)>1:
                max_lwfspins = [m.get_max_loop_particle_spin() for m in \
                                                                matrix_elements]
                max_loop_vert_ranks = [me.get_max_loop_vertex_rank() for me in \
                                                                matrix_elements]
                if len(set(max_lwfspins))>1 or len(set(max_loop_vert_ranks))>1:
                    self._curr_exporter.fix_coef_specs(max(max_lwfspins),\
                                                       max(max_loop_vert_ranks))
                    logger.warning('ML5 has just output processes which do not'+\
                      ' share the same maximum loop wavefunction size or the '+\
                      ' same maximum loop vertex rank. This is potentially '+\
                      ' dangerous. Please prefer to output them separately.')

        # Just the matrix.f files
        if self._export_format == 'matrix':
            for me in matrix_elements:
                filename = pjoin(path, 'matrix_' + \
                           me.get('processes')[0].shell_string() + ".f")
                if os.path.isfile(filename):
                    logger.warning("Overwriting existing file %s" % filename)
                else:
                    logger.info("Creating new file %s" % filename)
                calls = calls + self._curr_exporter.write_matrix_element_v4(\
                    writers.FortranWriter(filename),\
                    me, self._curr_fortran_model)
                
        cpu_time2 = time.time() - cpu_time1

        logger.info(("Generated helas calls for %d subprocesses " + \
              "(%d diagrams) in %0.3f s") % \
              (len(matrix_elements),
               ndiags, cpu_time))

        if calls:
            if "cpu_time2" in locals():
                logger.info("Wrote files for %d OPP calls in %0.3f s" % \
                            (calls, cpu_time2))
            else:
                logger.info("Wrote files for %d OPP calls" % \
                            (calls))

        # Replace the amplitudes with the actual amplitudes from the
        # matrix elements, which allows proper diagram drawing also of
        # decay chain processes
        self._curr_amps = diagram_generation.AmplitudeList(\
               [me.get('base_amplitude') for me in \
                matrix_elements])

    def ML5finalize(self, nojpeg, online = False):
        """Copy necessary sources and output the ps representation of 
        the diagrams, if needed"""

        if self._export_format in ['standalone']:
            logger.info('Export UFO model to MG4 format')
            # wanted_lorentz are the lorentz structures which are
            # actually used in the wavefunctions and amplitudes in
            # these processes
            wanted_lorentz = self._curr_matrix_elements.get_used_lorentz()
            wanted_couplings = self._curr_matrix_elements.get_used_couplings()
            self._curr_exporter.convert_model_to_mg4(self._curr_model,
                                           wanted_lorentz,
                                           wanted_couplings)

        if self._export_format in ['standalone']:
            self._curr_exporter.finalize_v4_directory( \
                                           self._curr_matrix_elements,
                                           self.history,
                                           not nojpeg,
                                           online,
                                           self.options['fortran_compiler'])

        if self._export_format in ['standalone']:
            logger.info('Output to directory ' + self._export_dir + ' done.')

    def do_launch(self, line, *args,**opt):
        """Main commands: Check that the type of launch is fine before proceeding with the
        mother function. """
                
        args = self.split_arg(line)
        # check argument validity and normalise argument
        (options, args) = mg_interface._launch_parser.parse_args(args)

        self.check_launch(args, options)

        if not args[0].startswith('standalone'):
            raise self.InvalidCmd('ML5 can only launch standalone runs.')

        start_cwd = os.getcwd()
        options = options.__dict__
        # args is now MODE PATH
        
        ext_program = launch_ext.MadLoopLauncher(self, args[1], \
                                                options=self.options, **options)
        ext_program.run()
        os.chdir(start_cwd) #ensure to go to the initial path
        
    def do_check(self, line, *args,**opt):
        """Check a given process or set of processes"""

        argss = self.split_arg(line, *args,**opt)
        # Check args validity
        self.validate_model()
        param_card = self.check_check(argss)
        reuse = argss[1]=="-reuse"   
        argss = argss[:1]+argss[2:]
        # For the stability check the user can specify the statistics (i.e
        # number of trial PS points) as a second argument
        if argss[0] in ['stability', 'profile']:
            stab_statistics = int(argss[1])
            argss = argss[:1]+argss[2:]
        # Now make sure the process is acceptable
        proc = " ".join(argss[1:-1])
        myprocdef = self.extract_process(proc)
        self.validate_model('virtual')
        self.proc_validity(myprocdef,'ML5_check')
        
        return mg_interface.MadGraphCmd.do_check(self, line, *args,**opt)
    
    def do_add(self, line, *args,**opt):
        """Generate an amplitude for a given process and add to
        existing amplitudes
        """
        args = self.split_arg(line)
        
        # Check the validity of the arguments
        self.check_add(args)
        self.validate_model()

        if args[0] == 'process':            
            # Rejoin line
            line = ' '.join(args[1:])
            
            # store the first process (for the perl script)
            if not self._generate_info:
                self._generate_info = line
                
            # Reset Helas matrix elements
            self._curr_matrix_elements = helas_objects.HelasMultiProcess()

            # Extract process from process definition
            self.validate_model('virtual')
            if ',' in line:
                myprocdef, line = self.extract_decay_chain_process(line)
            else:
                myprocdef = self.extract_process(line)
            self.proc_validity(myprocdef,'ML5')

            cpu_time1 = time.time()

            # Decide here wether one needs a LoopMultiProcess or a MultiProcess
            multiprocessclass=None
            if myprocdef['perturbation_couplings']!=[]:
                multiprocessclass=loop_diagram_generation.LoopMultiProcess
            else:
                multiprocessclass=diagram_generation.MultiProcess

            myproc = multiprocessclass(myprocdef, collect_mirror_procs = False,
                                       ignore_six_quark_processes = False)

            for amp in myproc.get('amplitudes'):
                if amp not in self._curr_amps:
                    self._curr_amps.append(amp)
                else:
                    warning = "Warning: Already in processes:\n%s" % \
                                                amp.nice_string_processes()
                    logger.warning(warning)


            # Reset _done_export, since we have new process
            self._done_export = False

            cpu_time2 = time.time()

            ndiags = sum([len(amp.get('loop_diagrams')) for \
                              amp in myproc.get('amplitudes')])
            logger.info("Process generated in %0.3f s" % \
                  (cpu_time2 - cpu_time1))
   
class LoopInterfaceWeb(mg_interface.CheckValidForCmdWeb, LoopInterface):
    pass

