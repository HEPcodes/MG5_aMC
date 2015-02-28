################################################################################
#
# Copyright (c) 2011 The MadGraph5_aMC@NLO Development team and Contributors
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
"""A user friendly command line interface to access MadGraph5_aMC@NLO features.
   Uses the cmd package for command interpretation and tab completion.
"""
from __future__ import division

import atexit
import glob
import logging
import math
import optparse
import os
import pydoc
import random
import re
import shutil
import subprocess
import sys
import traceback
import time
import signal
import tarfile
import copy
import datetime
import tarfile

try:
    import readline
    GNU_SPLITTING = ('GNU' in readline.__doc__)
except:
    GNU_SPLITTING = True

root_path = os.path.split(os.path.dirname(os.path.realpath( __file__ )))[0]
root_path = os.path.split(root_path)[0]
sys.path.insert(0, os.path.join(root_path,'bin'))

# usefull shortcut
pjoin = os.path.join
# Special logger for the Cmd Interface
logger = logging.getLogger('madgraph.stdout') # -> stdout
logger_stderr = logging.getLogger('madgraph.stderr') # ->stderr
 
try:
    # import from madgraph directory
    import madgraph.interface.extended_cmd as cmd
    import madgraph.interface.common_run_interface as common_run
    import madgraph.iolibs.files as files
    import madgraph.iolibs.save_load_object as save_load_object
    import madgraph.various.banner as banner_mod
    import madgraph.various.cluster as cluster
    import madgraph.various.misc as misc
    import madgraph.various.gen_crossxhtml as gen_crossxhtml
    import madgraph.various.sum_html as sum_html
    import madgraph.various.shower_card as shower_card
    import madgraph.various.FO_analyse_card as analyse_card

    from madgraph import InvalidCmd, aMCatNLOError, MadGraph5Error
    aMCatNLO = False
except ImportError, error:
    logger.debug(error)
    # import from madevent directory
    import internal.extended_cmd as cmd
    import internal.common_run_interface as common_run
    import internal.banner as banner_mod
    import internal.misc as misc    
    from internal import InvalidCmd, MadGraph5Error
    import internal.files as files
    import internal.cluster as cluster
    import internal.save_load_object as save_load_object
    import internal.gen_crossxhtml as gen_crossxhtml
    import internal.sum_html as sum_html
    import internal.shower_card as shower_card
    import internal.FO_analyse_card as analyse_card
    aMCatNLO = True

class aMCatNLOError(Exception):
    pass


def compile_dir(arguments):
    """compile the direcory p_dir
    arguments is the tuple (me_dir, p_dir, mode, options, tests, exe, run_mode)
    this function needs not to be a class method in order to do
    the compilation on multicore"""

    (me_dir, p_dir, mode, options, tests, exe, run_mode) = arguments
    logger.info(' Compiling %s...' % p_dir)

    this_dir = pjoin(me_dir, 'SubProcesses', p_dir) 

    try:
        #compile everything
        # compile and run tests
        for test in tests:
            misc.compile([test], cwd = this_dir, job_specs = False)
            input = pjoin(me_dir, '%s_input.txt' % test)
            #this can be improved/better written to handle the output
            misc.call(['./%s' % (test)], cwd=this_dir, 
                    stdin = open(input), stdout=open(pjoin(this_dir, '%s.log' % test), 'w'))
            
        if not options['reweightonly']:
            misc.compile(['gensym'], cwd=this_dir, job_specs = False)
            open(pjoin(this_dir, 'gensym_input.txt'), 'w').write('%s\n' % run_mode)
            misc.call(['./gensym'],cwd= this_dir,
                     stdin=open(pjoin(this_dir, 'gensym_input.txt')),
                     stdout=open(pjoin(this_dir, 'gensym.log'), 'w')) 
            #compile madevent_mintMC/mintFO
            misc.compile([exe], cwd=this_dir, job_specs = False)
        if mode in ['aMC@NLO', 'aMC@LO', 'noshower', 'noshowerLO']:
            misc.compile(['reweight_xsec_events'], cwd=this_dir, job_specs = False)

        logger.info('    %s done.' % p_dir) 
        return 0
    except MadGraph5Error, msg:
        return msg


def check_compiler(options, block=False):
    """check that the current fortran compiler is gfortran 4.6 or later.
    If block, stops the execution, otherwise just print a warning"""

    msg = 'In order to be able to run at NLO MadGraph5_aMC@NLO, you need to have ' + \
            'gfortran 4.6 or later installed.\n%s has been detected\n'+\
            'Note that You can still run all MadEvent run without any problem!'
    #first check that gfortran is installed
    if options['fortran_compiler']:
        compiler = options['fortran_compiler']
    elif misc.which('gfortran'):
        compiler = 'gfortran'
    else: 
        compiler = ''
        
    if 'gfortran' not in compiler:
        if block:
            raise aMCatNLOError(msg % compiler)
        else:
            logger.warning(msg % compiler)
    else:
        curr_version = misc.get_gfortran_version(compiler)
        if not ''.join(curr_version.split('.')) >= '46':
            if block:
                raise aMCatNLOError(msg % (compiler + ' ' + curr_version))
            else:
                logger.warning(msg % (compiler + ' ' + curr_version))
            


#===============================================================================
# CmdExtended
#===============================================================================
class CmdExtended(common_run.CommonRunCmd):
    """Particularisation of the cmd command for aMCatNLO"""

    #suggested list of command
    next_possibility = {
        'start': [],
    }
    
    debug_output = 'ME5_debug'
    error_debug = 'Please report this bug on https://bugs.launchpad.net/madgraph5\n'
    error_debug += 'More information is found in \'%(debug)s\'.\n' 
    error_debug += 'Please attach this file to your report.'

    config_debug = 'If you need help with this issue please contact us on https://answers.launchpad.net/madgraph5\n'


    keyboard_stop_msg = """stopping all operation
            in order to quit MadGraph5_aMC@NLO please enter exit"""
    
    # Define the Error
    InvalidCmd = InvalidCmd
    ConfigurationError = aMCatNLOError

    def __init__(self, me_dir, options, *arg, **opt):
        """Init history and line continuation"""
        
        # Tag allowing/forbiding question
        self.force = False
        
        # If possible, build an info line with current version number 
        # and date, from the VERSION text file
        info = misc.get_pkg_info()
        info_line = ""
        if info and info.has_key('version') and  info.has_key('date'):
            len_version = len(info['version'])
            len_date = len(info['date'])
            if len_version + len_date < 30:
                info_line = "#*         VERSION %s %s %s         *\n" % \
                            (info['version'],
                            (30 - len_version - len_date) * ' ',
                            info['date'])
        else:
            version = open(pjoin(root_path,'MGMEVersion.txt')).readline().strip()
            info_line = "#*         VERSION %s %s                *\n" % \
                            (version, (24 - len(version)) * ' ')    

        # Create a header for the history file.
        # Remember to fill in time at writeout time!
        self.history_header = \
        '#************************************************************\n' + \
        '#*                    MadGraph5_aMC@NLO                     *\n' + \
        '#*                                                          *\n' + \
        "#*                *                       *                 *\n" + \
        "#*                  *        * *        *                   *\n" + \
        "#*                    * * * * 5 * * * *                     *\n" + \
        "#*                  *        * *        *                   *\n" + \
        "#*                *                       *                 *\n" + \
        "#*                                                          *\n" + \
        "#*                                                          *\n" + \
        info_line + \
        "#*                                                          *\n" + \
        "#*    The MadGraph5_aMC@NLO Development Team - Find us at   *\n" + \
        "#*    https://server06.fynu.ucl.ac.be/projects/madgraph     *\n" + \
        "#*                           and                            *\n" + \
        "#*                http://amcatnlo.cern.ch                   *\n" + \
        '#*                                                          *\n' + \
        '#************************************************************\n' + \
        '#*                                                          *\n' + \
        '#*               Command File for aMCatNLO                  *\n' + \
        '#*                                                          *\n' + \
        '#*     run as ./bin/aMCatNLO.py filename                    *\n' + \
        '#*                                                          *\n' + \
        '#************************************************************\n'
        
        if info_line:
            info_line = info_line[1:]

        logger.info(\
        "************************************************************\n" + \
        "*                                                          *\n" + \
        "*           W E L C O M E  to  M A D G R A P H 5           *\n" + \
        "*                       a M C @ N L O                      *\n" + \
        "*                                                          *\n" + \
        "*                 *                       *                *\n" + \
        "*                   *        * *        *                  *\n" + \
        "*                     * * * * 5 * * * *                    *\n" + \
        "*                   *        * *        *                  *\n" + \
        "*                 *                       *                *\n" + \
        "*                                                          *\n" + \
        info_line + \
        "*                                                          *\n" + \
        "*    The MadGraph5_aMC@NLO Development Team - Find us at   *\n" + \
        "*                 http://amcatnlo.cern.ch                  *\n" + \
        "*                                                          *\n" + \
        "*               Type 'help' for in-line help.              *\n" + \
        "*                                                          *\n" + \
        "************************************************************")
        super(CmdExtended, self).__init__(me_dir, options, *arg, **opt)
        

    def get_history_header(self):
        """return the history header""" 
        return self.history_header % misc.get_time_info()
    
    def stop_on_keyboard_stop(self):
        """action to perform to close nicely on a keyboard interupt"""
        try:
            if hasattr(self, 'cluster'):
                logger.info('rm jobs on queue')
                self.cluster.remove()
            if hasattr(self, 'results'):
                self.update_status('Stop by the user', level=None, makehtml=True, error=True)
                self.add_error_log_in_html(KeyboardInterrupt)
        except:
            pass
    
    def postcmd(self, stop, line):
        """ Update the status of  the run for finishing interactive command """
        
        # relaxing the tag forbidding question
        self.force = False
        
        if not self.use_rawinput:
            return stop
        
        
        arg = line.split()
        if  len(arg) == 0:
            return stop
        elif str(arg[0]) in ['exit','quit','EOF']:
            return stop
        
        try:
            self.update_status('Command \'%s\' done.<br> Waiting for instruction.' % arg[0], 
                               level=None, error=True)
        except Exception:
            misc.sprint('self.update_status fails', log=logger)
            pass
            
    def nice_user_error(self, error, line):
        """If a ME run is currently running add a link in the html output"""

        self.add_error_log_in_html()
        cmd.Cmd.nice_user_error(self, error, line)            
        
    def nice_config_error(self, error, line):
        """If a ME run is currently running add a link in the html output"""

        self.add_error_log_in_html()
        cmd.Cmd.nice_config_error(self, error, line)

    def nice_error_handling(self, error, line):
        """If a ME run is currently running add a link in the html output"""

        self.add_error_log_in_html()            
        cmd.Cmd.nice_error_handling(self, error, line)

        
        
#===============================================================================
# HelpToCmd
#===============================================================================
class HelpToCmd(object):
    """ The Series of help routine for the aMCatNLOCmd"""
    
    def help_launch(self):
        """help for launch command"""
        _launch_parser.print_help()

    def help_banner_run(self):
        logger.info("syntax: banner_run Path|RUN [--run_options]")
        logger.info("-- Reproduce a run following a given banner")
        logger.info("   One of the following argument is require:")
        logger.info("   Path should be the path of a valid banner.")
        logger.info("   RUN should be the name of a run of the current directory")
        self.run_options_help([('-f','answer all question by default'),
                               ('--name=X', 'Define the name associated with the new run')]) 


    def help_compile(self):
        """help for compile command"""
        _compile_parser.print_help()

    def help_generate_events(self):
        """help for generate_events commandi
        just call help_launch"""
        _generate_events_parser.print_help()


    def help_calculate_xsect(self):
        """help for generate_events command"""
        _calculate_xsect_parser.print_help()

    def help_shower(self):
        """help for shower command"""
        _shower_parser.print_help()

    
    def help_open(self):
        logger.info("syntax: open FILE  ")
        logger.info("-- open a file with the appropriate editor.")
        logger.info('   If FILE belongs to index.html, param_card.dat, run_card.dat')
        logger.info('   the path to the last created/used directory is used')

    def run_options_help(self, data):
        if data:
            logger.info('-- local options:')
            for name, info in data:
                logger.info('      %s : %s' % (name, info))
        
        logger.info("-- session options:")
        logger.info("      Note that those options will be kept for the current session")      
        logger.info("      --cluster : Submit to the  cluster. Current cluster: %s" % self.options['cluster_type'])
        logger.info("      --multicore : Run in multi-core configuration")
        logger.info("      --nb_core=X : limit the number of core to use to X.")
        


       
#===============================================================================
# CheckValidForCmd
#===============================================================================
class CheckValidForCmd(object):
    """ The Series of check routine for the aMCatNLOCmd"""

    def check_shower(self, args, options):
        """Check the validity of the line. args[0] is the run_directory"""
        
        if options['force']:
            self.force = True
        
        if len(args) == 0:
            self.help_shower()
            raise self.InvalidCmd, 'Invalid syntax, please specify the run name'
        if not os.path.isdir(pjoin(self.me_dir, 'Events', args[0])):
            raise self.InvalidCmd, 'Directory %s does not exists' % \
                            pjoin(os.getcwd(), 'Events',  args[0])

        self.set_run_name(args[0], level= 'shower')
        args[0] = pjoin(self.me_dir, 'Events', args[0])
    
    def check_plot(self, args):
        """Check the argument for the plot command
        plot run_name modes"""


        madir = self.options['madanalysis_path']
        td = self.options['td_path']
        
        if not madir or not td:
            logger.info('Retry to read configuration file to find madanalysis/td')
            self.set_configuration()

        madir = self.options['madanalysis_path']
        td = self.options['td_path']        
        
        if not madir:
            error_msg = 'No Madanalysis path correctly set.'
            error_msg += 'Please use the set command to define the path and retry.'
            error_msg += 'You can also define it in the configuration file.'
            raise self.InvalidCmd(error_msg)  
        if not  td:
            error_msg = 'No path to td directory correctly set.'
            error_msg += 'Please use the set command to define the path and retry.'
            error_msg += 'You can also define it in the configuration file.'
            raise self.InvalidCmd(error_msg)  
                     
        if len(args) == 0:
            if not hasattr(self, 'run_name') or not self.run_name:
                self.help_plot()
                raise self.InvalidCmd('No run name currently define. Please add this information.')             
            args.append('all')
            return

        
        if args[0] not in self._plot_mode:
            self.set_run_name(args[0], level='plot')
            del args[0]
            if len(args) == 0:
                args.append('all')
        elif not self.run_name:
            self.help_plot()
            raise self.InvalidCmd('No run name currently define. Please add this information.')                             
        
        for arg in args:
            if arg not in self._plot_mode and arg != self.run_name:
                 self.help_plot()
                 raise self.InvalidCmd('unknown options %s' % arg)        
    
    def check_pgs(self, arg):
        """Check the argument for pythia command
        syntax: pgs [NAME] 
        Note that other option are already remove at this point
        """
        
        # If not pythia-pgs path
        if not self.options['pythia-pgs_path']:
            logger.info('Retry to read configuration file to find pythia-pgs path')
            self.set_configuration()
      
        if not self.options['pythia-pgs_path'] or not \
            os.path.exists(pjoin(self.options['pythia-pgs_path'],'src')):
            error_msg = 'No pythia-pgs path correctly set.'
            error_msg += 'Please use the set command to define the path and retry.'
            error_msg += 'You can also define it in the configuration file.'
            raise self.InvalidCmd(error_msg)          
        
        tag = [a for a in arg if a.startswith('--tag=')]
        if tag: 
            arg.remove(tag[0])
            tag = tag[0][6:]
        
        
        if len(arg) == 0 and not self.run_name:
            if self.results.lastrun:
                arg.insert(0, self.results.lastrun)
            else:
                raise self.InvalidCmd('No run name currently define. Please add this information.')             
        
        if len(arg) == 1 and self.run_name == arg[0]:
            arg.pop(0)
        
        if not len(arg) and \
           not os.path.exists(pjoin(self.me_dir,'Events','pythia_events.hep')):
            self.help_pgs()
            raise self.InvalidCmd('''No file file pythia_events.hep currently available
            Please specify a valid run_name''')
                
        lock = None              
        if len(arg) == 1:
            prev_tag = self.set_run_name(arg[0], tag, 'pgs')
            filenames = glob.glob(pjoin(self.me_dir, 'Events', self.run_name,
                                            'events_*.hep.gz'))
            if not filenames:
                raise self.InvalidCmd('No events file corresponding to %s run with tag %s. '% (self.run_name, prev_tag))
            else:
                input_file = filenames[0]
                output_file = pjoin(self.me_dir, 'Events', 'pythia_events.hep')
                lock = cluster.asyncrone_launch('gunzip',stdout=open(output_file,'w'), 
                                                    argument=['-c', input_file])
        else:
            if tag: 
                self.run_card['run_tag'] = tag
            self.set_run_name(self.run_name, tag, 'pgs')
        
        return lock
            

    def check_delphes(self, arg):
        """Check the argument for pythia command
        syntax: delphes [NAME] 
        Note that other option are already remove at this point
        """
        
        # If not pythia-pgs path
        if not self.options['delphes_path']:
            logger.info('Retry to read configuration file to find delphes path')
            self.set_configuration()
      
        if not self.options['delphes_path']:
            error_msg = 'No delphes path correctly set.'
            error_msg += 'Please use the set command to define the path and retry.'
            error_msg += 'You can also define it in the configuration file.'
            raise self.InvalidCmd(error_msg)  

        tag = [a for a in arg if a.startswith('--tag=')]
        if tag: 
            arg.remove(tag[0])
            tag = tag[0][6:]
            
                  
        if len(arg) == 0 and not self.run_name:
            if self.results.lastrun:
                arg.insert(0, self.results.lastrun)
            else:
                raise self.InvalidCmd('No run name currently define. Please add this information.')             
        
        if len(arg) == 1 and self.run_name == arg[0]:
            arg.pop(0)
        
        if not len(arg) and \
           not os.path.exists(pjoin(self.me_dir,'Events','pythia_events.hep')):
            self.help_pgs()
            raise self.InvalidCmd('''No file file pythia_events.hep currently available
            Please specify a valid run_name''')
                              
        if len(arg) == 1:
            prev_tag = self.set_run_name(arg[0], tag, 'delphes')
            filenames = glob.glob(pjoin(self.me_dir, 'Events', self.run_name,
                                            'events_*.hep.gz'))
            if not filenames:
                raise self.InvalidCmd('No events file corresponding to %s run with tag %s.:%s '\
                    % (self.run_name, prev_tag, 
                       pjoin(self.me_dir,'Events',self.run_name, '%s_pythia_events.hep.gz' % prev_tag)))
            else:
                input_file = filenames[0]
                output_file = pjoin(self.me_dir, 'Events', 'pythia_events.hep')
                lock = cluster.asyncrone_launch('gunzip',stdout=open(output_file,'w'), 
                                                    argument=['-c', input_file])
        else:
            if tag:
                self.run_card['run_tag'] = tag
            self.set_run_name(self.run_name, tag, 'delphes')               

    def check_calculate_xsect(self, args, options):
        """check the validity of the line. args is ORDER,
        ORDER being LO or NLO. If no mode is passed, NLO is used"""
        # modify args in order to be DIR 
        # mode being either standalone or madevent
        
        if options['force']:
            self.force = True
        
        if not args:
            args.append('NLO')
            return
        
        if len(args) > 1:
            self.help_calculate_xsect()
            raise self.InvalidCmd, 'Invalid Syntax: Too many argument'

        elif len(args) == 1:
            if not args[0] in ['NLO', 'LO']:
                raise self.InvalidCmd, '%s is not a valid mode, please use "LO" or "NLO"' % args[1]
        mode = args[0]
        
        # check for incompatible options/modes
        if options['multicore'] and options['cluster']:
            raise self.InvalidCmd, 'options -m (--multicore) and -c (--cluster)' + \
                    ' are not compatible. Please choose one.'


    def check_generate_events(self, args, options):
        """check the validity of the line. args is ORDER,
        ORDER being LO or NLO. If no mode is passed, NLO is used"""
        # modify args in order to be DIR 
        # mode being either standalone or madevent
        
        if not args:
            args.append('NLO')
            return
        
        if len(args) > 1:
            self.help_generate_events()
            raise self.InvalidCmd, 'Invalid Syntax: Too many argument'

        elif len(args) == 1:
            if not args[0] in ['NLO', 'LO']:
                raise self.InvalidCmd, '%s is not a valid mode, please use "LO" or "NLO"' % args[1]
        mode = args[0]
        
        # check for incompatible options/modes
        if options['multicore'] and options['cluster']:
            raise self.InvalidCmd, 'options -m (--multicore) and -c (--cluster)' + \
                    ' are not compatible. Please choose one.'

    def check_banner_run(self, args):
        """check the validity of line"""
        
        if len(args) == 0:
            self.help_banner_run()
            raise self.InvalidCmd('banner_run requires at least one argument.')
        
        tag = [a[6:] for a in args if a.startswith('--tag=')]
        
        
        if os.path.exists(args[0]):
            type ='banner'
            format = self.detect_card_type(args[0])
            if format != 'banner':
                raise self.InvalidCmd('The file is not a valid banner.')
        elif tag:
            args[0] = pjoin(self.me_dir,'Events', args[0], '%s_%s_banner.txt' % \
                                    (args[0], tag))                  
            if not os.path.exists(args[0]):
                raise self.InvalidCmd('No banner associates to this name and tag.')
        else:
            name = args[0]
            type = 'run'
            banners = glob.glob(pjoin(self.me_dir,'Events', args[0], '*_banner.txt'))
            if not banners:
                raise self.InvalidCmd('No banner associates to this name.')    
            elif len(banners) == 1:
                args[0] = banners[0]
            else:
                #list the tag and propose those to the user
                tags = [os.path.basename(p)[len(args[0])+1:-11] for p in banners]
                tag = self.ask('which tag do you want to use?', tags[0], tags)
                args[0] = pjoin(self.me_dir,'Events', args[0], '%s_%s_banner.txt' % \
                                    (args[0], tag))                
                        
        run_name = [arg[7:] for arg in args if arg.startswith('--name=')]
        if run_name:
            try:
                self.exec_cmd('remove %s all banner -f' % run_name)
            except Exception:
                pass
            self.set_run_name(args[0], tag=None, level='parton', reload_card=True)
        elif type == 'banner':
            self.set_run_name(self.find_available_run_name(self.me_dir))
        elif type == 'run':
            if not self.results[name].is_empty():
                run_name = self.find_available_run_name(self.me_dir)
                logger.info('Run %s is not empty so will use run_name: %s' % \
                                                               (name, run_name))
                self.set_run_name(run_name)
            else:
                try:
                    self.exec_cmd('remove %s all banner -f' % run_name)
                except Exception:
                    pass
                self.set_run_name(name)



    def check_launch(self, args, options):
        """check the validity of the line. args is MODE
        MODE being LO, NLO, aMC@NLO or aMC@LO. If no mode is passed, auto is used"""
        # modify args in order to be DIR 
        # mode being either standalone or madevent
        
        if options['force']:
            self.force = True
        
        
        if not args:
            args.append('auto')
            return
        
        if len(args) > 1:
            self.help_launch()
            raise self.InvalidCmd, 'Invalid Syntax: Too many argument'

        elif len(args) == 1:
            if not args[0] in ['LO', 'NLO', 'aMC@NLO', 'aMC@LO','auto']:
                raise self.InvalidCmd, '%s is not a valid mode, please use "LO", "NLO", "aMC@NLO" or "aMC@LO"' % args[0]
        mode = args[0]
        
        # check for incompatible options/modes
        if options['multicore'] and options['cluster']:
            raise self.InvalidCmd, 'options -m (--multicore) and -c (--cluster)' + \
                    ' are not compatible. Please choose one.'
        if mode == 'NLO' and options['reweightonly']:
            raise self.InvalidCmd, 'option -r (--reweightonly) needs mode "aMC@NLO" or "aMC@LO"'


    def check_compile(self, args, options):
        """check the validity of the line. args is MODE
        MODE being FO or MC. If no mode is passed, MC is used"""
        # modify args in order to be DIR 
        # mode being either standalone or madevent
        
        if options['force']:
            self.force = True
        
        if not args:
            args.append('MC')
            return
        
        if len(args) > 1:
            self.help_compile()
            raise self.InvalidCmd, 'Invalid Syntax: Too many argument'

        elif len(args) == 1:
            if not args[0] in ['MC', 'FO']:
                raise self.InvalidCmd, '%s is not a valid mode, please use "FO" or "MC"' % args[0]
        mode = args[0]
        
        # check for incompatible options/modes


#===============================================================================
# CompleteForCmd
#===============================================================================
class CompleteForCmd(CheckValidForCmd):
    """ The Series of help routine for the MadGraphCmd"""

    def complete_launch(self, text, line, begidx, endidx):
        """auto-completion for launch command"""
        
        args = self.split_arg(line[0:begidx])
        if len(args) == 1:
            #return mode
            return self.list_completion(text,['LO','NLO','aMC@NLO','aMC@LO'],line)
        elif len(args) == 2 and line[begidx-1] == '@':
            return self.list_completion(text,['LO','NLO'],line)
        else:
            opts = []
            for opt in _launch_parser.option_list:
                opts += opt._long_opts + opt._short_opts
            return self.list_completion(text, opts, line)
           
    def complete_banner_run(self, text, line, begidx, endidx):
       "Complete the banner run command"
       try:
  
        
        args = self.split_arg(line[0:begidx], error=False)
        
        if args[-1].endswith(os.path.sep):
            return self.path_completion(text,
                                        os.path.join('.',*[a for a in args \
                                                    if a.endswith(os.path.sep)]))        
        
        
        if len(args) > 1:
            # only options are possible
            tags = glob.glob(pjoin(self.me_dir, 'Events' , args[1],'%s_*_banner.txt' % args[1]))
            tags = ['%s' % os.path.basename(t)[len(args[1])+1:-11] for t in tags]

            if args[-1] != '--tag=':
                tags = ['--tag=%s' % t for t in tags]
            else:
                return self.list_completion(text, tags)
            return self.list_completion(text, tags +['--name=','-f'], line)
        
        # First argument
        possibilites = {} 

        comp = self.path_completion(text, os.path.join('.',*[a for a in args \
                                                    if a.endswith(os.path.sep)]))
        if os.path.sep in line:
            return comp
        else:
            possibilites['Path from ./'] = comp

        run_list =  glob.glob(pjoin(self.me_dir, 'Events', '*','*_banner.txt'))
        run_list = [n.rsplit('/',2)[1] for n in run_list]
        possibilites['RUN Name'] = self.list_completion(text, run_list)
        
        return self.deal_multiple_categories(possibilites)
    
        
       except Exception, error:
           print error

 
    def complete_compile(self, text, line, begidx, endidx):
        """auto-completion for launch command"""
        
        args = self.split_arg(line[0:begidx])
        if len(args) == 1:
            #return mode
            return self.list_completion(text,['FO','MC'],line)
        else:
            opts = []
            for opt in _compile_parser.option_list:
                opts += opt._long_opts + opt._short_opts
            return self.list_completion(text, opts, line)        

    def complete_calculate_xsect(self, text, line, begidx, endidx):
        """auto-completion for launch command"""
        
        args = self.split_arg(line[0:begidx])
        if len(args) == 1:
            #return mode
            return self.list_completion(text,['LO','NLO'],line)
        else:
            opts = []
            for opt in _calculate_xsect_parser.option_list:
                opts += opt._long_opts + opt._short_opts
            return self.list_completion(text, opts, line) 

    def complete_generate_events(self, text, line, begidx, endidx):
        """auto-completion for generate_events command
        call the compeltion for launch"""
        self.complete_launch(text, line, begidx, endidx)


    def complete_shower(self, text, line, begidx, endidx):
        args = self.split_arg(line[0:begidx])
        if len(args) == 1:
            #return valid run_name
            data = glob.glob(pjoin(self.me_dir, 'Events', '*','events.lhe.gz'))
            data = [n.rsplit('/',2)[1] for n in data]
            tmp1 =  self.list_completion(text, data)
            if not self.run_name:
                return tmp1

    def complete_plot(self, text, line, begidx, endidx):
        """ Complete the plot command """
        
        args = self.split_arg(line[0:begidx], error=False)

        if len(args) == 1:
            #return valid run_name
            data = glob.glob(pjoin(self.me_dir, 'Events', '*','events.lhe*'))
            data = [n.rsplit('/',2)[1] for n in data]
            tmp1 =  self.list_completion(text, data)
            if not self.run_name:
                return tmp1

        if len(args) > 1:
            return self.list_completion(text, self._plot_mode)        

    def complete_pgs(self,text, line, begidx, endidx):
        "Complete the pgs command"
        args = self.split_arg(line[0:begidx], error=False) 
        if len(args) == 1:
            #return valid run_name
            data = glob.glob(pjoin(self.me_dir, 'Events', '*', 'events_*.hep.gz'))
            data = [n.rsplit('/',2)[1] for n in data]
            tmp1 =  self.list_completion(text, data)
            if not self.run_name:
                return tmp1
            else:
                tmp2 = self.list_completion(text, self._run_options + ['-f', 
                                                '--tag=' ,'--no_default'], line)
                return tmp1 + tmp2        
        else:
            return self.list_completion(text, self._run_options + ['-f', 
                                                 '--tag=','--no_default'], line)

    complete_delphes = complete_pgs        

class aMCatNLOAlreadyRunning(InvalidCmd):
    pass

#===============================================================================
# aMCatNLOCmd
#===============================================================================
class aMCatNLOCmd(CmdExtended, HelpToCmd, CompleteForCmd, common_run.CommonRunCmd):
    """The command line processor of MadGraph"""    
    
    # Truth values
    true = ['T','.true.',True,'true']
    # Options and formats available
    _run_options = ['--cluster','--multicore','--nb_core=','--nb_core=2', '-c', '-m']
    _generate_options = ['-f', '--laststep=parton', '--laststep=pythia', '--laststep=pgs', '--laststep=delphes']
    _calculate_decay_options = ['-f', '--accuracy=0.']
    _set_options = ['stdout_level','fortran_compiler','cpp_compiler','timeout']
    _plot_mode = ['all', 'parton','shower','pgs','delphes']
    _clean_mode = _plot_mode + ['channel', 'banner']
    _display_opts = ['run_name', 'options', 'variable']
    # survey options, dict from name to type, default value, and help text
    # Variables to store object information
    web = False
    cluster_mode = 0
    queue  = 'madgraph'
    nb_core = None
    
    next_possibility = {
        'start': ['generate_events [OPTIONS]', 'calculate_crossx [OPTIONS]', 'launch [OPTIONS]',
                  'help generate_events'],
        'generate_events': ['generate_events [OPTIONS]', 'shower'],
        'launch': ['launch [OPTIONS]', 'shower'],
        'shower' : ['generate_events [OPTIONS]']
    }
    
    
    ############################################################################
    def __init__(self, me_dir = None, options = {}, *completekey, **stdin):
        """ add information to the cmd """

        self.start_time = 0
        CmdExtended.__init__(self, me_dir, options, *completekey, **stdin)
        #common_run.CommonRunCmd.__init__(self, me_dir, options)

        self.mode = 'aMCatNLO'
        self.nb_core = 0
        self.prompt = "%s>"%os.path.basename(pjoin(self.me_dir))

        # load the current status of the directory
        if os.path.exists(pjoin(self.me_dir,'HTML','results.pkl')):
            self.results = save_load_object.load_from_file(pjoin(self.me_dir,'HTML','results.pkl'))
            self.results.resetall(self.me_dir)
            self.last_mode = self.results[self.results.lastrun][-1]['run_mode']
        else:
            model = self.find_model_name()
            process = self.process # define in find_model_name
            self.results = gen_crossxhtml.AllResultsNLO(model, process, self.me_dir)
            self.last_mode = ''
        self.results.def_web_mode(self.web)
        # check that compiler is gfortran 4.6 or later if virtuals have been exported
        proc_card = open(pjoin(self.me_dir, 'Cards', 'proc_card_mg5.dat')).read()

        if not '[real=QCD]' in proc_card:
            check_compiler(self.options, block=True)

        
    ############################################################################      
    def do_shower(self, line):
        """ run the shower on a given parton level file """
        argss = self.split_arg(line)
        (options, argss) = _launch_parser.parse_args(argss)
        # check argument validity and normalise argument
        options = options.__dict__
        options['reweightonly'] = False
        self.check_shower(argss, options)
        evt_file = pjoin(os.getcwd(), argss[0], 'events.lhe')
        self.ask_run_configuration('onlyshower', options)
        self.run_mcatnlo(evt_file)

        self.update_status('', level='all', update_results=True)

    ################################################################################
    def do_plot(self, line):
        """Create the plot for a given run"""

        # Since in principle, all plot are already done automaticaly
        args = self.split_arg(line)
        # Check argument's validity
        self.check_plot(args)
        logger.info('plot for run %s' % self.run_name)
        
        if not self.force:
            self.ask_edit_cards([], args, plot=True)
                
        if any([arg in ['parton'] for arg in args]):
            filename = pjoin(self.me_dir, 'Events', self.run_name, 'events.lhe')
            if os.path.exists(filename+'.gz'):
                misc.gunzip(filename)
            if  os.path.exists(filename):
                logger.info('Found events.lhe file for run %s' % self.run_name) 
                shutil.move(filename, pjoin(self.me_dir, 'Events', 'unweighted_events.lhe'))
                self.create_plot('parton')
                shutil.move(pjoin(self.me_dir, 'Events', 'unweighted_events.lhe'), filename)
                misc.gzip(filename)
                
        if any([arg in ['all','parton'] for arg in args]):
            filename = pjoin(self.me_dir, 'Events', self.run_name, 'MADatNLO.top')
            if  os.path.exists(filename):
                logger.info('Found MADatNLO.top file for run %s' % \
                             self.run_name) 
                output = pjoin(self.me_dir, 'HTML',self.run_name, 'plots_parton.html')
                plot_dir = pjoin(self.me_dir, 'HTML', self.run_name, 'plots_parton')
                
                if not os.path.isdir(plot_dir):
                    os.makedirs(plot_dir) 
                top_file = pjoin(plot_dir, 'plots.top')
                files.cp(filename, top_file)
                madir = self.options['madanalysis_path']
                tag = self.run_card['run_tag']  
                td = self.options['td_path']
                misc.call(['%s/plot' % self.dirbin, madir, td],
                                stdout = open(pjoin(plot_dir, 'plot.log'),'a'),
                                stderr = subprocess.STDOUT,
                                cwd=plot_dir)

                misc.call(['%s/plot_page-pl' % self.dirbin, 
                                    os.path.basename(plot_dir),
                                    'parton'],
                                stdout = open(pjoin(plot_dir, 'plot.log'),'a'),
                                stderr = subprocess.STDOUT,
                                cwd=pjoin(self.me_dir, 'HTML', self.run_name))
                shutil.move(pjoin(self.me_dir, 'HTML',self.run_name ,'plots.html'),
                                                                             output)

                os.remove(pjoin(self.me_dir, 'Events', 'plots.top'))
                
        if any([arg in ['all','shower'] for arg in args]):
            filenames = glob.glob(pjoin(self.me_dir, 'Events', self.run_name,
                                        'events_*.lhe.gz'))
            if len(filenames) != 1:
                filenames = glob.glob(pjoin(self.me_dir, 'Events', self.run_name,
                                            'events_*.hep.gz'))
                if len(filenames) != 1:
                    logger.info('No shower level file found for run %s' % \
                                self.run_name)
                    return
                filename = filenames[0]
                misc.gunzip(filename, keep=True, stdout=pjoin(self.me_dir, 'Events','pythia_events.hep'))
                
                if not os.path.exists(pjoin(self.me_dir, 'Cards', 'pythia_card.dat')):
                    if aMCatNLO and not self.options['mg5_path']:
                        raise "plotting NLO HEP file needs MG5 utilities"
                    
                    files.cp(pjoin(self.options['mg5_path'], 'Template','LO', 'Cards', 'pythia_card_default.dat'),
                             pjoin(self.me_dir, 'Cards', 'pythia_card.dat'))
                self.run_hep2lhe()
            else:
                filename = filenames[0]
                misc.gunzip(filename, keep=True, stdout=pjoin(self.me_dir, 'Events','pythia_events.hep'))

            self.create_plot('shower')
            lhe_file_name = filename.replace('.hep.gz', '.lhe')
            shutil.move(pjoin(self.me_dir, 'Events','pythia_events.lhe'), 
                        lhe_file_name)
            misc.gzip(lhe_file_name)
                    
        if any([arg in ['all','pgs'] for arg in args]):
            filename = pjoin(self.me_dir, 'Events', self.run_name, 
                                            '%s_pgs_events.lhco' % self.run_tag)
            if os.path.exists(filename+'.gz'):
                misc.gunzip(filename)
            if  os.path.exists(filename):
                self.create_plot('PGS')
                misc.gzip(filename)                
            else:
                logger.info('No valid files for pgs plot')
                
        if any([arg in ['all','delphes'] for arg in args]):
            filename = pjoin(self.me_dir, 'Events', self.run_name, 
                                        '%s_delphes_events.lhco' % self.run_tag)
            if os.path.exists(filename+'.gz'):
                misc.gunzip(filename)
            if  os.path.exists(filename):
                #shutil.move(filename, pjoin(self.me_dir, 'Events','delphes_events.lhco'))
                self.create_plot('Delphes')
                #shutil.move(pjoin(self.me_dir, 'Events','delphes_events.lhco'), filename)
                misc.gzip(filename)                
            else:
                logger.info('No valid files for delphes plot')


    ############################################################################      
    def do_calculate_xsect(self, line):
        """Main commands: calculates LO/NLO cross-section, using madevent_mintFO 
        this function wraps the do_launch one"""
        
        self.start_time = time.time()
        argss = self.split_arg(line)
        # check argument validity and normalise argument
        (options, argss) = _calculate_xsect_parser.parse_args(argss)
        options = options.__dict__
        options['reweightonly'] = False
        options['parton'] = True
        self.check_calculate_xsect(argss, options)
        self.do_launch(line, options, argss)
        
    ############################################################################
    def do_banner_run(self, line): 
        """Make a run from the banner file"""
        
        args = self.split_arg(line)
        #check the validity of the arguments
        self.check_banner_run(args)    
                     
        # Remove previous cards
        for name in ['shower_card.dat', 'madspin_card.dat']:
            try:
                os.remove(pjoin(self.me_dir, 'Cards', name))
            except Exception:
                pass
            
        banner_mod.split_banner(args[0], self.me_dir, proc_card=False)
        
        # Check if we want to modify the run
        if not self.force:
            ans = self.ask('Do you want to modify the Cards/Run Type?', 'n', ['y','n'])
            if ans == 'n':
                self.force = True
        
        # Compute run mode:
        if self.force:
            mode_status = {'order': 'NLO', 'fixed_order': False, 'madspin':False, 'shower':True}
            banner = banner_mod.Banner(args[0])
            for line in banner['run_settings']:
                if '=' in line:
                    mode, value = [t.strip() for t in line.split('=')]
                    mode_status[mode] = value
        else:
            mode_status = {}

        # Call Generate events
        self.do_launch('-n %s %s' % (self.run_name, '-f' if self.force else ''),
                       switch=mode_status)
        
    ############################################################################      
    def do_generate_events(self, line):
        """Main commands: generate events  
        this function just wraps the do_launch one"""
        self.do_launch(line)


    ############################################################################
    def do_treatcards(self, line, amcatnlo=True):
        """Advanced commands: this is for creating the correct run_card.inc from the nlo format"""
                #check if no 'Auto' are present in the file
        self.check_param_card(pjoin(self.me_dir, 'Cards','param_card.dat'))
        return super(aMCatNLOCmd,self).do_treatcards(line, amcatnlo)
    
    ############################################################################
    def set_configuration(self, amcatnlo=True, **opt):
        """assign all configuration variable from file 
            loop over the different config file if config_file not define """
        return super(aMCatNLOCmd,self).set_configuration(amcatnlo=amcatnlo, **opt)
    
    ############################################################################      
    def do_launch(self, line, options={}, argss=[], switch={}):
        """Main commands: launch the full chain 
        options and args are relevant if the function is called from other 
        functions, such as generate_events or calculate_xsect
        mode gives the list of switch needed for the computation (usefull for banner_run)
        """
        
        if not argss and not options:
            self.start_time = time.time()
            argss = self.split_arg(line)
            # check argument validity and normalise argument
            (options, argss) = _launch_parser.parse_args(argss)
            options = options.__dict__
            self.check_launch(argss, options)

        if 'run_name' in options.keys() and options['run_name']:
            self.run_name = options['run_name']
            # if a dir with the given run_name already exists
            # remove it and warn the user
            if os.path.isdir(pjoin(self.me_dir, 'Events', self.run_name)):
                logger.warning('Removing old run information in \n'+
                                pjoin(self.me_dir, 'Events', self.run_name))
                files.rm(pjoin(self.me_dir, 'Events', self.run_name))
                self.results.delete_run(self.run_name)

        if options['multicore']:
            self.cluster_mode = 2
        elif options['cluster']:
            self.cluster_mode = 1
        
        if not switch:
            mode = argss[0]
            if mode in ['LO', 'NLO']:
                options['parton'] = True
            mode = self.ask_run_configuration(mode, options)
        else:
            mode = self.ask_run_configuration('auto', options, switch)

        self.results.add_detail('run_mode', mode) 

        self.update_status('Starting run', level=None, update_results=True)

        if self.options['automatic_html_opening']:
            misc.open_file(os.path.join(self.me_dir, 'crossx.html'))
            self.options['automatic_html_opening'] = False

        if '+' in mode:
            mode = mode.split('+')[0]
        self.compile(mode, options) 
        evt_file = self.run(mode, options)
        
        if int(self.run_card['nevents']) == 0 and not mode in ['LO', 'NLO']:
            logger.info('No event file generated: grids have been set-up with a '\
                            'relative precision of %s' % self.run_card['req_acc'])
            return

        if not mode in ['LO', 'NLO']:
            assert evt_file == pjoin(self.me_dir,'Events', self.run_name, 'events.lhe'), '%s != %s' %(evt_file, pjoin(self.me_dir,'Events', self.run_name, 'events.lhe.gz'))
            self.exec_cmd('decay_events -from_cards', postcmd=False)
            evt_file = pjoin(self.me_dir,'Events', self.run_name, 'events.lhe')
        
        if not mode in ['LO', 'NLO', 'noshower', 'noshowerLO'] \
                                                      and not options['parton']:
            self.run_mcatnlo(evt_file)
        elif mode == 'noshower':
            logger.warning("""You have chosen not to run a parton shower. NLO events without showering are NOT physical.
Please, shower the Les Houches events before using them for physics analyses.""")


        self.update_status('', level='all', update_results=True)
        if int(self.run_card['ickkw']) == 3 and mode in ['noshower', 'aMC@NLO']:
            logger.warning("""You are running with FxFx merging enabled.
To be able to merge samples of various multiplicities without double counting,
you have to remove some events after showering 'by hand'.
Please read http://amcatnlo.cern.ch/FxFx_merging.htm for more details.""")



    ############################################################################      
    def do_compile(self, line):
        """Advanced commands: just compile the executables """
        argss = self.split_arg(line)
        # check argument validity and normalise argument
        (options, argss) = _compile_parser.parse_args(argss)
        options = options.__dict__
        options['reweightonly'] = False
        options['nocompile'] = False
        self.check_compile(argss, options)
        
        mode = {'FO': 'NLO', 'MC': 'aMC@NLO'}[argss[0]]
        self.ask_run_configuration(mode, options)
        self.compile(mode, options) 


        self.update_status('', level='all', update_results=True)

    def print_results_in_shell(self, data):
        """Have a nice results prints in the shell,
        data should be of type: gen_crossxhtml.OneTagResults"""
        if not data:
            return
        logger.info("  === Results Summary for run: %s tag: %s ===\n" % (data['run_name'],data['tag']))
        if self.ninitial == 1:
            logger.info("     Width :   %.4g +- %.4g GeV" % (data['cross'], data['error']))
        else:
            logger.info("     Cross-section :   %.4g +- %.4g pb" % (data['cross'], data['error']))
        logger.info("     Nb of events :  %s" % data['nb_event'] )
        #if data['cross_pythia'] and data['nb_event_pythia']:
        #    if self.ninitial == 1:
        #        logger.info("     Matched Width :   %.4g +- %.4g GeV" % (data['cross_pythia'], data['error_pythia']))
        #    else:
        #        logger.info("     Matched Cross-section :   %.4g +- %.4g pb" % (data['cross_pythia'], data['error_pythia']))            
        #    logger.info("     Nb of events after Matching :  %s" % data['nb_event_pythia'])
        #    if self.run_card['use_syst'] in self.true:
        #        logger.info("     Be carefull that matched information are here NOT for the central value. Refer to SysCalc output for it")    
        logger.info(" " )

    def print_results_in_file(self, data, path, mode='w'):
        """Have a nice results prints in the shell,
        data should be of type: gen_crossxhtml.OneTagResults"""
        if not data:
            return
        
        fsock = open(path, mode)
        
        fsock.write("  === Results Summary for run: %s tag: %s  process: %s ===\n" % \
                    (data['run_name'],data['tag'], os.path.basename(self.me_dir)))
        
        if self.ninitial == 1:
            fsock.write("     Width :   %.4g +- %.4g GeV\n" % (data['cross'], data['error']))
        else:
            fsock.write("     Cross-section :   %.4g +- %.4g pb\n" % (data['cross'], data['error']))
        fsock.write("     Nb of events :  %s\n" % data['nb_event'] )
        #if data['cross_pythia'] and data['nb_event_pythia']:
        #    if self.ninitial == 1:
        #        fsock.write("     Matched Width :   %.4g +- %.4g GeV\n" % (data['cross_pythia'], data['error_pythia']))
        #    else:
        #        fsock.write("     Matched Cross-section :   %.4g +- %.4g pb\n" % (data['cross_pythia'], data['error_pythia']))            
        #    fsock.write("     Nb of events after Matching :  %s\n" % data['nb_event_pythia'])
        fsock.write(" \n" )





    def update_random_seed(self):
        """Update random number seed with the value from the run_card. 
        If this is 0, update the number according to a fresh one"""
        iseed = int(self.run_card['iseed'])
        if iseed == 0:
            randinit = open(pjoin(self.me_dir, 'SubProcesses', 'randinit'))
            iseed = int(randinit.read()[2:]) + 1
            randinit.close()
        randinit = open(pjoin(self.me_dir, 'SubProcesses', 'randinit'), 'w')
        randinit.write('r=%d' % iseed)
        randinit.close()


    def get_characteristics(self, file):
        """reads the proc_characteristics file and initialises the correspondant
        dictionary"""
        lines = [l for l in open(file).read().split('\n') if l and not l.startswith('#')]
        self.proc_characteristics = {}
        for l in lines:
            key, value = l.split('=')
            self.proc_characteristics[key.strip()] = value.strip()
            
        
    def run(self, mode, options):
        """runs aMC@NLO. Returns the name of the event file created"""
        logger.info('Starting run')

        if not 'only_generation' in options.keys():
            options['only_generation'] = False

        if mode in ['LO', 'NLO'] and self.run_card['iappl'] == '2' and not options['only_generation']:
            options['only_generation'] = True
        self.get_characteristics(pjoin(self.me_dir, 'SubProcesses', 'proc_characteristics'))

        if self.cluster_mode == 1:
            cluster_name = self.options['cluster_type']
            self.cluster = cluster.from_name[cluster_name](**self.options)
        if self.cluster_mode == 2:
            try:
                import multiprocessing
                if not self.nb_core:
                    try:
                        self.nb_core = int(self.options['nb_core'])
                    except TypeError:
                        self.nb_core = multiprocessing.cpu_count()
                logger.info('Using %d cores' % self.nb_core)
            except ImportError:
                self.nb_core = 1
                logger.warning('Impossible to detect the number of cores => Using One.\n'+
                        'Use set nb_core X in order to set this number and be able to'+
                        'run in multicore.')

            self.cluster = cluster.MultiCore(**self.options)
        self.update_random_seed()
        #find and keep track of all the jobs
        folder_names = {'LO': ['born_G*'], 'NLO': ['all_G*'],
                    'aMC@LO': ['GB*'], 'aMC@NLO': ['GF*']}
        folder_names['noshower'] = folder_names['aMC@NLO']
        folder_names['noshowerLO'] = folder_names['aMC@LO']
        job_dict = {}
        p_dirs = [d for d in \
                open(pjoin(self.me_dir, 'SubProcesses', 'subproc.mg')).read().split('\n') if d]
        #find jobs and clean previous results
        if not options['only_generation'] and not options['reweightonly']:
            self.update_status('Cleaning previous results', level=None)
        for dir in p_dirs:
            job_dict[dir] = [file for file in \
                                 os.listdir(pjoin(self.me_dir, 'SubProcesses', dir)) \
                                 if file.startswith('ajob')] 
            #find old folders to be removed
            for obj in folder_names[mode]:
                to_rm = [file for file in \
                             os.listdir(pjoin(self.me_dir, 'SubProcesses', dir)) \
                             if file.startswith(obj[:-1]) and \
                            (os.path.isdir(pjoin(self.me_dir, 'SubProcesses', dir, file)) or \
                             os.path.exists(pjoin(self.me_dir, 'SubProcesses', dir, file)))] 
                #always clean dirs for the splitted event generation
                # do not include the born_G/ grid_G which should be kept when
                # doing a f.o. run keeping old grids
                to_always_rm = [file for file in \
                             os.listdir(pjoin(self.me_dir, 'SubProcesses', dir)) \
                             if file.startswith(obj[:-1]) and
                             '_' in file and not '_G' in file and \
                            (os.path.isdir(pjoin(self.me_dir, 'SubProcesses', dir, file)) or \
                             os.path.exists(pjoin(self.me_dir, 'SubProcesses', dir, file)))]

                if not options['only_generation'] and not options['reweightonly']:
                    to_always_rm.extend(to_rm)
                    if os.path.exists(pjoin(self.me_dir, 'SubProcesses', dir,'MadLoop5_resources.tar.gz')):
                        to_always_rm.append(pjoin(self.me_dir, 'SubProcesses', dir,'MadLoop5_resources.tar.gz'))
                files.rm([pjoin(self.me_dir, 'SubProcesses', dir, d) for d in to_always_rm])

        mcatnlo_status = ['Setting up grid', 'Computing upper envelope', 'Generating events']

        if self.run_card['iappl']=='2':
            self.applgrid_distribute(options,mode,p_dirs)

        if options['reweightonly']:
            event_norm=self.run_card['event_norm']
            nevents=int(self.run_card['nevents'])
            return self.reweight_and_collect_events(options, mode, nevents, event_norm)

        devnull = os.open(os.devnull, os.O_RDWR) 
        if mode in ['LO', 'NLO']:
            # this is for fixed order runs
            mode_dict = {'NLO': 'all', 'LO': 'born'}
            logger.info('Doing fixed order %s' % mode)
            req_acc = self.run_card['req_acc_FO']
            if not options['only_generation'] and req_acc != '-1':
                self.write_madin_file(pjoin(self.me_dir, 'SubProcesses'), mode_dict[mode], 0, '-1', '6','0.10') 
                self.update_status('Setting up grids', level=None)
                self.run_all(job_dict, [['0', mode_dict[mode], '0']], 'Setting up grids')
            elif not options['only_generation']:
                npoints = self.run_card['npoints_FO_grid']
                niters = self.run_card['niters_FO_grid']
                self.write_madin_file(pjoin(self.me_dir, 'SubProcesses'), mode_dict[mode], 0, npoints, niters) 
                self.update_status('Setting up grids', level=None)
                self.run_all(job_dict, [['0', mode_dict[mode], '0']], 'Setting up grids')

            npoints = self.run_card['npoints_FO']
            niters = self.run_card['niters_FO']
            self.write_madin_file(pjoin(self.me_dir, 'SubProcesses'), mode_dict[mode], -1, npoints, niters) 
            # collect the results and logs
            self.collect_log_files(folder_names[mode], 0)
            p = misc.Popen(['./combine_results_FO.sh', req_acc, '%s_G*' % mode_dict[mode]], \
                               stdout=subprocess.PIPE, \
                               cwd=pjoin(self.me_dir, 'SubProcesses'))
            output = p.communicate()

            self.cross_sect_dict = self.read_results(output, mode)
            self.print_summary(options, 0, mode)
            cross, error = sum_html.make_all_html_results(self, ['%s*' % mode_dict[mode]])
            self.results.add_detail('cross', cross)
            self.results.add_detail('error', error) 

            self.update_status('Computing cross-section', level=None)
            self.run_all(job_dict, [['0', mode_dict[mode], '0', mode_dict[mode]]], 'Computing cross-section')

            # collect the results and logs
            self.collect_log_files(folder_names[mode], 1)
            p = misc.Popen(['./combine_results_FO.sh', '-1'] + folder_names[mode], \
                                stdout=subprocess.PIPE, 
                                cwd=pjoin(self.me_dir, 'SubProcesses'))
            output = p.communicate()
            self.cross_sect_dict = self.read_results(output, mode)

            # collect the scale and PDF uncertainties
            scale_pdf_info={}
            if self.run_card['reweight_scale'] == '.true.' or self.run_card['reweight_PDF'] == '.true.':
                data_files=[]
                for dir in p_dirs:
                    for obj in folder_names[mode]:
                        for file in os.listdir(pjoin(self.me_dir, 'SubProcesses', dir)):
                            if file.startswith(obj[:-1]) and \
                                    (os.path.exists(pjoin(self.me_dir, 'SubProcesses', dir, file,'scale_pdf_dependence.dat'))):
                                data_files.append(pjoin(dir,file,'scale_pdf_dependence.dat'))
                scale_pdf_info = self.pdf_scale_from_reweighting(data_files)
            # print the results:
            self.print_summary(options, 1, mode, scale_pdf_info)

            files.cp(pjoin(self.me_dir, 'SubProcesses', 'res.txt'),
                     pjoin(self.me_dir, 'Events', self.run_name))
            
            if self.analyse_card['fo_analysis_format'].lower() == 'topdrawer':
                misc.call(['./combine_plots_FO.sh'] + folder_names[mode], \
                                stdout=devnull, 
                                cwd=pjoin(self.me_dir, 'SubProcesses'))
                files.cp(pjoin(self.me_dir, 'SubProcesses', 'MADatNLO.top'),
                                pjoin(self.me_dir, 'Events', self.run_name))
                logger.info('The results of this run and the TopDrawer file with the plots' + \
                        ' have been saved in %s' % pjoin(self.me_dir, 'Events', self.run_name))
            elif self.analyse_card['fo_analysis_format'].lower() == 'root':
                misc.call(['./combine_root.sh'] + folder_names[mode], \
                                stdout=devnull, 
                                cwd=pjoin(self.me_dir, 'SubProcesses'))
                files.cp(pjoin(self.me_dir, 'SubProcesses', 'MADatNLO.root'),
                                pjoin(self.me_dir, 'Events', self.run_name))
                logger.info('The results of this run and the ROOT file with the plots' + \
                        ' have been saved in %s' % pjoin(self.me_dir, 'Events', self.run_name))
            else:
                logger.info('The results of this run' + \
                            ' have been saved in %s' % pjoin(self.me_dir, 'Events', self.run_name))
                
            cross, error = sum_html.make_all_html_results(self, folder_names[mode])
            self.results.add_detail('cross', cross)
            self.results.add_detail('error', error)
            if self.run_card['iappl'] != '0':
                self.applgrid_combine(cross,error)
            self.update_status('Run complete', level='parton', update_results=True)

            return

        elif mode in ['aMC@NLO','aMC@LO','noshower','noshowerLO']:
            shower = self.run_card['parton_shower'].upper()
            nevents = int(self.run_card['nevents'])
            req_acc = self.run_card['req_acc']
            if nevents == 0 and float(req_acc) < 0 :
                raise aMCatNLOError('Cannot determine the required accuracy from the number '\
                                        'of events, because 0 events requested. Please set '\
                                        'the "req_acc" parameter in the run_card to a value between 0 and 1')
            elif float(req_acc) >1 or float(req_acc) == 0 :
                raise aMCatNLOError('Required accuracy ("req_acc" in the run_card) should '\
                                        'be between larger than 0 and smaller than 1, '\
                                        'or set to -1 for automatic determination. Current value is %s' % req_acc)
# For more than 1M events, set req_acc to 0.001 (except when it was explicitly set in the run_card)
            elif float(req_acc) < 0 and nevents > 1000000 :
                req_acc='0.001'

            shower_list = ['HERWIG6', 'HERWIGPP', 'PYTHIA6Q', 'PYTHIA6PT', 'PYTHIA8']

            if not shower in shower_list:
                raise aMCatNLOError('%s is not a valid parton shower. Please use one of the following: %s' \
                    % (shower, ', '.join(shower_list)))

# check that PYTHIA6PT is not used for processes with FSR
            if shower == 'PYTHIA6PT' and \
                self.proc_characteristics['has_fsr'] == 'true':
                raise aMCatNLOError('PYTHIA6PT does not support processes with FSR')

            if mode in ['aMC@NLO', 'aMC@LO']:
                logger.info('Doing %s matched to parton shower' % mode[4:])
            elif mode in ['noshower','noshowerLO']:
                logger.info('Generating events without running the shower.')
            elif options['only_generation']:
                logger.info('Generating events starting from existing results')
            

            for i, status in enumerate(mcatnlo_status):
                #check if need to split jobs 
                # at least one channel must have enough events
                try:
                    nevents_unweighted = open(pjoin(self.me_dir, 
                                                'SubProcesses', 
                                                'nevents_unweighted')).read().split('\n')
                except IOError:
                    nevents_unweighted = []

                split = i == 2 and \
                        int(self.run_card['nevt_job']) > 0 

                if i == 2 or not options['only_generation']:
                    # if the number of events requested is zero,
                    # skip mint step 2
                    if i==2 and nevents==0:
                        self.print_summary(options, 2,mode)
                        return

                    if split:
                        # split the event generation
                        misc.call([pjoin(self.me_dir, 'bin', 'internal', 'split_jobs.py')] + \
                                   [self.run_card['nevt_job']],
                                   stdout = devnull,
                                   cwd = pjoin(self.me_dir, 'SubProcesses'))
                        assert os.path.exists(pjoin(self.me_dir, 'SubProcesses', 
                            'nevents_unweighted_splitted'))

                    self.update_status(status, level='parton')
                    if mode in ['aMC@NLO', 'noshower']:
                        self.write_madinMMC_file(pjoin(self.me_dir, 'SubProcesses'), 'all', i) 
                        self.run_all(job_dict, [['2', 'F', '%d' % i]], status, split_jobs = split)
                        
                    elif mode in ['aMC@LO', 'noshowerLO']:
                        self.write_madinMMC_file(
                            pjoin(self.me_dir, 'SubProcesses'), 'born', i) 
                        self.run_all(job_dict, 
                                     [['2', 'B', '%d' % i]], 
                                     '%s at LO' % status, split_jobs = split)

                if (i < 2 and not options['only_generation']) or i == 1 :
                    # collect the results and logs
                    self.collect_log_files(folder_names[mode], i)
                    p = misc.Popen(['./combine_results.sh'] + \
                                   ['%d' % i,'%d' % nevents, '%s' % req_acc ] + \
                                   folder_names[mode],
                                   stdout=subprocess.PIPE, 
                                   cwd = pjoin(self.me_dir, 'SubProcesses'))
                    output = p.communicate()
                    files.cp(pjoin(self.me_dir, 'SubProcesses', 'res_%d.txt' % i), \
                             pjoin(self.me_dir, 'Events', self.run_name))

                    self.cross_sect_dict = self.read_results(output, mode)
                    self.print_summary(options, i, mode)

                    cross, error = sum_html.make_all_html_results(self, folder_names[mode])
                    self.results.add_detail('cross', cross)
                    self.results.add_detail('error', error) 

                #check that split jobs are all correctly terminated
                if split:
                    self.check_event_files()

        if self.cluster_mode == 1:
            #if cluster run, wait 15 sec so that event files are transferred back
            self.update_status(
                    'Waiting while files are transferred back from the cluster nodes',
                    level='parton')
            time.sleep(10)
        if split:
            files.cp(pjoin(self.me_dir, 'SubProcesses', 'nevents_unweighted_splitted'), \
                     pjoin(self.me_dir, 'SubProcesses', 'nevents_unweighted'))


        event_norm=self.run_card['event_norm']
        self.collect_log_files(folder_names[mode], 2)
        return self.reweight_and_collect_events(options, mode, nevents, event_norm)


    def applgrid_combine(self,cross,error):
        """Combines the APPLgrids in all the SubProcess/P*/all_G*/ directories"""
        logger.debug('Combining APPLgrids \n')
        applcomb=pjoin(self.options['applgrid'].rstrip('applgrid-config'),'applgrid-combine')
        with open(pjoin(self.me_dir,'SubProcesses','dirs.txt')) as dirf:
            all_jobs=dirf.readlines()
        ngrids=len(all_jobs)
        nobs  =len([name for name in os.listdir(pjoin(self.me_dir,'SubProcesses',all_jobs[0].rstrip())) \
                        if name.endswith("_out.root")])
        for obs in range(0,nobs):
            gdir = [pjoin(self.me_dir,'SubProcesses',job.rstrip(),"grid_obs_"+str(obs)+"_out.root") for job in all_jobs]
            # combine APPLgrids from different channels for observable 'obs'
            if self.run_card["iappl"] == "1":
                misc.call([applcomb,'-o', pjoin(self.me_dir,"Events",self.run_name,"aMCfast_obs_"+str(obs)+"_starting_grid.root"), '--optimise']+ gdir)
            elif self.run_card["iappl"] == "2":
                unc2_inv=pow(cross/error,2)
                unc2_inv_ngrids=pow(cross/error,2)*ngrids
                misc.call([applcomb,'-o', pjoin(self.me_dir,"Events",self.run_name,"aMCfast_obs_"+str(obs)+".root"),'-s',str(unc2_inv),'--weight',str(unc2_inv)]+ gdir)
                for job in all_jobs:
                    os.remove(pjoin(self.me_dir,'SubProcesses',job.rstrip(),"grid_obs_"+str(obs)+"_in.root"))
            else:
                raise aMCatNLOError('iappl parameter can only be 0, 1 or 2')
            # after combining, delete the original grids
            for ggdir in gdir:
                os.remove(ggdir)

        
    def applgrid_distribute(self,options,mode,p_dirs):
        """Distributes the APPLgrids ready to be filled by a second run of the code"""
        # if no appl_start_grid argument given, guess it from the time stamps of the starting grid files
        if not('appl_start_grid' in options.keys() and options['appl_start_grid']):
            gfiles=glob.glob(pjoin(self.me_dir, 'Events','*','aMCfast_obs_0_starting_grid.root'))
            time_stamps={}
            for root_file in gfiles:
                time_stamps[root_file]=os.path.getmtime(root_file)
            options['appl_start_grid']= \
                max(time_stamps.iterkeys(), key=(lambda key: time_stamps[key])).split('/')[-2]
            logger.info('No --appl_start_grid option given. Guessing that start grid from run "%s" should be used.' \
                            % options['appl_start_grid'])

        if 'appl_start_grid' in options.keys() and options['appl_start_grid']:
            self.appl_start_grid = options['appl_start_grid']
            start_grid_dir=pjoin(self.me_dir, 'Events', self.appl_start_grid)
            # check that this dir exists and at least one grid file is there
            if not os.path.exists(pjoin(start_grid_dir,'aMCfast_obs_0_starting_grid.root')):
                raise self.InvalidCmd('APPLgrid file not found: %s' % \
                                  pjoin(start_grid_dir,'aMCfast_obs_0_starting_grid.root'))
            else:
                all_grids=[pjoin(start_grid_dir,name) for name in os.listdir(start_grid_dir) \
                               if name.endswith("_starting_grid.root")]
                nobs =len(all_grids)
                gstring=" ".join(all_grids)
        if not hasattr(self, 'appl_start_grid') or not self.appl_start_grid:
            raise self.InvalidCmd('No APPLgrid name currently defined. Please provide this information.')             
        if mode == 'NLO':
            gdir='all_G'
        elif mode == 'LO':
            gdir='born_G'
        #copy the grid to all relevant directories
        for pdir in p_dirs:
            g_dirs = [file for file in os.listdir(pjoin(self.me_dir,"SubProcesses",pdir)) \
                      if file.startswith(gdir) and os.path.isdir(pjoin(self.me_dir,"SubProcesses",pdir, file))]
            for g_dir in g_dirs:
                for grid in all_grids:
                    obs=grid.split('_')[-3]
                    files.cp(grid,pjoin(self.me_dir,"SubProcesses",pdir,g_dir,'grid_obs_'+obs+'_in.root'))


    def collect_log_files(self, folders, istep):
        """collect the log files and put them in a single, html-friendly file inside the run_...
        directory"""
        step_list = ['Grid setting', 'Cross-section computation', 'Event generation']
        log_file = pjoin(self.me_dir, 'Events', self.run_name, 
                'alllogs_%d.html' % istep)
        # this keeps track of which step has been computed for which channel
        channel_dict = {}
        log_files = []
        for folder in folders:
            log_files += glob.glob(pjoin(self.me_dir, 'SubProcesses', 'P*', folder, 'log.txt'))

        content = ''

        content += '<HTML><BODY>\n<font face="courier" size=2>'
        for log in log_files:
            channel_dict[os.path.dirname(log)] = [istep]
            # put an anchor
            content += '<a name=%s></a>\n' % (os.path.dirname(log).replace(pjoin(self.me_dir,'SubProcesses'),''))
            # and put some nice header
            content += '<font color="red">\n'
            content += '<br>LOG file for integration channel %s, %s <br>' % \
                    (os.path.dirname(log).replace(pjoin(self.me_dir,'SubProcesses'), ''), 
                     step_list[istep])
            content += '</font>\n'
            #then just flush the content of the small log inside the big log
            #the PRE tag prints everything verbatim
            content += '<PRE>\n' + open(log).read() + '\n</PRE>'
            content +='<br>\n'

        content += '</font>\n</BODY></HTML>\n'
        open(log_file, 'w').write(content)


    def read_results(self, output, mode):
        """extract results (cross-section, absolute cross-section and errors)
        from output, which should be formatted as
            Found 4 correctly terminated jobs 
            random seed found in 'randinit' is 33
            Integrated abs(cross-section)
            7.94473937e+03 +- 2.9953e+01  (3.7702e-01%)
             Integrated cross-section
            6.63392298e+03 +- 3.7669e+01  (5.6782e-01%)
        for aMC@NLO/aMC@LO, and as

        for NLO/LO
        The cross_sect_dict is returned"""
        res = {}
        if mode in ['aMC@LO', 'aMC@NLO', 'noshower', 'noshowerLO']:
            pat = re.compile(\
'''Found (\d+) correctly terminated jobs 
random seed found in 'randinit' is (\d+)
Integrated abs\(cross-section\)
\s*(\d+\.\d+e[+-]\d+) \+\- (\d+\.\d+e[+-]\d+)  \((\d+\.\d+e[+-]\d+)\%\)
Integrated cross-section
\s*(\-?\d+\.\d+e[+-]\d+) \+\- (\d+\.\d+e[+-]\d+)  \((\-?\d+\.\d+e[+-]\d+)\%\)''')
        else:
            pat = re.compile(\
'''Found (\d+) correctly terminated jobs 
\s*(\-?\d+\.\d+e[+-]\d+) \+\- (\d+\.\d+e[+-]\d+)  \((\-?\d+\.\d+e[+-]\d+)\%\)''')
            pass

        match = re.search(pat, output[0])
        if not match or output[1]:
            logger.info('Return code of the event collection: '+str(output[1]))
            logger.info('Output of the event collection:\n'+output[0])
            raise aMCatNLOError('An error occurred during the collection of results.\n' + 
            'Please check the .log files inside the directories which failed.')
#        if int(match.groups()[0]) != self.njobs:
#            raise aMCatNLOError('Not all jobs terminated successfully')
        if mode in ['aMC@LO', 'aMC@NLO', 'noshower', 'noshowerLO']:
            return {'randinit' : int(match.groups()[1]),
                    'xseca' : float(match.groups()[2]),
                    'erra' : float(match.groups()[3]),
                    'xsect' : float(match.groups()[5]),
                    'errt' : float(match.groups()[6])}
        else:
            return {'xsect' : float(match.groups()[1]),
                    'errt' : float(match.groups()[2])}

    def print_summary(self, options, step, mode, scale_pdf_info={}):
        """print a summary of the results contained in self.cross_sect_dict.
        step corresponds to the mintMC step, if =2 (i.e. after event generation)
        some additional infos are printed"""
        # find process name
        proc_card_lines = open(pjoin(self.me_dir, 'Cards', 'proc_card_mg5.dat')).read().split('\n')
        process = ''
        for line in proc_card_lines:
            if line.startswith('generate') or line.startswith('add process'):
                process = process+(line.replace('generate ', '')).replace('add process ','')+' ; '
        lpp = {'0':'l', '1':'p', '-1':'pbar'}
        proc_info = '\n      Process %s\n      Run at %s-%s collider (%s + %s GeV)' % \
        (process[:-3], lpp[self.run_card['lpp1']], lpp[self.run_card['lpp2']], 
                self.run_card['ebeam1'], self.run_card['ebeam2'])
        
        # Gather some basic statistics for the run and extracted from the log files.
        if mode in ['aMC@NLO', 'aMC@LO', 'noshower', 'noshowerLO']: 
            log_GV_files =  glob.glob(pjoin(self.me_dir, \
                                    'SubProcesses', 'P*','G*','log_MINT*.txt'))
            all_log_files = glob.glob(pjoin(self.me_dir, \
                                          'SubProcesses', 'P*','G*','log*.txt'))
        elif mode == 'NLO':
            log_GV_files =  glob.glob(pjoin(self.me_dir, \
                                    'SubProcesses', 'P*','all_G*','log*.txt'))
            all_log_files = sum([glob.glob(pjoin(self.me_dir,'SubProcesses', 'P*',
              '%sG*'%foldName,'log*.txt')) for foldName in ['all_']],[])
        elif mode == 'LO':
            log_GV_files = ''
            all_log_files = sum([glob.glob(pjoin(self.me_dir,'SubProcesses', 'P*',
              '%sG*'%foldName,'log*.txt')) for foldName in ['born_']],[])
        else:
            raise aMCatNLOError, 'Running mode %s not supported.'%mode
            
        
        if mode in ['aMC@NLO', 'aMC@LO', 'noshower', 'noshowerLO']:
            status = ['Determining the number of unweighted events per channel',
                      'Updating the number of unweighted events per channel',
                      'Summary:']
            if step != 2:
                message = status[step] + '\n\n      Intermediate results:' + \
                    ('\n      Random seed: %(randinit)d' + \
                     '\n      Total cross-section:      %(xsect)8.3e +- %(errt)6.1e pb' + \
                     '\n      Total abs(cross-section): %(xseca)8.3e +- %(erra)6.1e pb \n') \
                     % self.cross_sect_dict
            else:
        
                message = '\n      ' + status[step] + proc_info + \
                          '\n      Total cross-section: %(xsect)8.3e +- %(errt)6.1e pb' % \
                        self.cross_sect_dict

                if int(self.run_card['nevents'])>=10000 and self.run_card['reweight_scale']=='.true.':
                   message = message + \
                       ('\n      Ren. and fac. scale uncertainty: +%0.1f%% -%0.1f%%') % \
                       (scale_pdf_info['scale_upp'], scale_pdf_info['scale_low'])
                if int(self.run_card['nevents'])>=10000 and self.run_card['reweight_PDF']=='.true.':
                   message = message + \
                       ('\n      PDF uncertainty: +%0.1f%% -%0.1f%%') % \
                       (scale_pdf_info['pdf_upp'], scale_pdf_info['pdf_low'])

                neg_frac = (self.cross_sect_dict['xseca'] - self.cross_sect_dict['xsect'])/\
                       (2. * self.cross_sect_dict['xseca'])
                message = message + \
                    ('\n      Number of events generated: %s' + \
                     '\n      Parton shower to be used: %s' + \
                     '\n      Fraction of negative weights: %4.2f' + \
                     '\n      Total running time : %s') % \
                        (self.run_card['nevents'],
                         self.run_card['parton_shower'],
                         neg_frac, 
                         misc.format_timer(time.time()-self.start_time))

        elif mode in ['NLO', 'LO']:
            status = ['Results after grid setup (cross-section is non-physical):',
                      'Final results and run summary:']
            if step == 0:
                message = '\n      ' + status[step] + \
                     '\n      Total cross-section:      %(xsect)8.3e +- %(errt)6.1e pb' % \
                             self.cross_sect_dict
            elif step == 1:
                message = '\n      ' + status[step] + proc_info + \
                     '\n      Total cross-section:      %(xsect)8.3e +- %(errt)6.1e pb' % \
                             self.cross_sect_dict
                if self.run_card['reweight_scale']=='.true.':
                    message = message + \
                        ('\n      Ren. and fac. scale uncertainty: +%0.1f%% -%0.1f%%') % \
                        (scale_pdf_info['scale_upp'], scale_pdf_info['scale_low'])
                if self.run_card['reweight_PDF']=='.true.':
                    message = message + \
                        ('\n      PDF uncertainty: +%0.1f%% -%0.1f%%') % \
                        (scale_pdf_info['pdf_upp'], scale_pdf_info['pdf_low'])
        
        if (mode in ['NLO', 'LO'] and step!=1) or \
           (mode in ['aMC@NLO', 'aMC@LO', 'noshower', 'noshowerLO'] and step!=2):
            logger.info(message+'\n')
            return

        # Some advanced general statistics are shown in the debug message at the
        # end of the run
        # Make sure it never stops a run
        try:
            message, debug_msg = \
               self.compile_advanced_stats(log_GV_files, all_log_files, message)
        except Exception as e:
            debug_msg = 'Advanced statistics collection failed with error "%s"'%str(e)

        logger.debug(debug_msg+'\n')
        logger.info(message+'\n')
        
        # Now copy relevant information in the Events/Run_<xxx> directory
        evt_path = pjoin(self.me_dir, 'Events', self.run_name)
        open(pjoin(evt_path, 'summary.txt'),'w').write(message+'\n')
        open(pjoin(evt_path, '.full_summary.txt'), 
                                       'w').write(message+'\n\n'+debug_msg+'\n')
                                       
        self.archive_files(evt_path,mode)

    def archive_files(self, evt_path, mode):
        """ Copies in the Events/Run_<xxx> directory relevant files characterizing
        the run."""

        files_to_arxiv = [pjoin('Cards','param_card.dat'),
                          pjoin('Cards','MadLoopParams.dat'),
                          pjoin('Cards','FKS_params.dat'),
                          pjoin('Cards','run_card.dat'),                          
                          pjoin('Subprocesses','setscales.f'),
                          pjoin('Subprocesses','cuts.f')]

        if mode in ['NLO', 'LO']:
            files_to_arxiv.append(pjoin('Cards','FO_analyse_card.dat'))

        if not os.path.exists(pjoin(evt_path,'RunMaterial')):
            os.mkdir(pjoin(evt_path,'RunMaterial'))

        for path in files_to_arxiv:
            if os.path.isfile(pjoin(self.me_dir,path)):
                files.cp(pjoin(self.me_dir,path),pjoin(evt_path,'RunMaterial'))
        misc.call(['tar','-czpf','RunMaterial.tar.gz','RunMaterial'],cwd=evt_path)
        shutil.rmtree(pjoin(evt_path,'RunMaterial'))

    def compile_advanced_stats(self,log_GV_files,all_log_files,message):
        """ This functions goes through the log files given in arguments and 
        compiles statistics about MadLoop stability, virtual integration 
        optimization and detection of potential error messages into a nice
        debug message to printed at the end of the run """
        
        # > UPS is a dictionary of tuples with this format {channel:[nPS,nUPS]}
        # > Errors is a list of tuples with this format (log_file,nErrors)
        stats = {'UPS':{}, 'Errors':[], 'virt_stats':{}, 'timings':{}}
        mint_search = re.compile(r"MINT(?P<ID>\d*).txt")

        # ==================================     
        # == MadLoop stability statistics ==
        # ==================================
    
        # Recuperate the fraction of unstable PS points found in the runs for
        # the virtuals
        UPS_stat_finder = re.compile(
             r"Satistics from MadLoop:.*"+\
             r"Total points tried\:\s+(?P<ntot>\d+).*"+\
             r"Stability unknown\:\s+(?P<nsun>\d+).*"+\
             r"Stable PS point\:\s+(?P<nsps>\d+).*"+\
             r"Unstable PS point \(and rescued\)\:\s+(?P<nups>\d+).*"+\
             r"Exceptional PS point \(unstable and not rescued\)\:\s+(?P<neps>\d+).*"+\
             r"Double precision used\:\s+(?P<nddp>\d+).*"+\
             r"Quadruple precision used\:\s+(?P<nqdp>\d+).*"+\
             r"Initialization phase\-space points\:\s+(?P<nini>\d+).*"+\
             r"Unknown return code \(100\)\:\s+(?P<n100>\d+).*"+\
             r"Unknown return code \(10\)\:\s+(?P<n10>\d+).*",re.DOTALL)
    
        unit_code_meaning = { 0 : 'Not identified (CTModeRun != -1)',
                              1 : 'CutTools (double precision)',
                              2 : 'PJFry++',
                              3 : 'IREGI',
                              4 : 'Golem95',
                              9 : 'CutTools (quadruple precision)'}
        RetUnit_finder =re.compile(
                           r"#Unit\s*(?P<unit>\d+)\s*=\s*(?P<n_occurences>\d+)")
    #Unit
    
        for gv_log in log_GV_files:
            channel_name = '/'.join(gv_log.split('/')[-5:-1])
            log=open(gv_log,'r').read()                
            UPS_stats = re.search(UPS_stat_finder,log)
            for retunit_stats in re.finditer(RetUnit_finder, log):
                if channel_name not in stats['UPS'].keys():
                    stats['UPS'][channel_name] = [0]*10+[[0]*10]
                stats['UPS'][channel_name][10][int(retunit_stats.group('unit'))] \
                                     += int(retunit_stats.group('n_occurences'))
            if not UPS_stats is None:
                try:
                    stats['UPS'][channel_name][0] += int(UPS_stats.group('ntot'))
                    stats['UPS'][channel_name][1] += int(UPS_stats.group('nsun'))
                    stats['UPS'][channel_name][2] += int(UPS_stats.group('nsps'))
                    stats['UPS'][channel_name][3] += int(UPS_stats.group('nups'))
                    stats['UPS'][channel_name][4] += int(UPS_stats.group('neps'))
                    stats['UPS'][channel_name][5] += int(UPS_stats.group('nddp'))
                    stats['UPS'][channel_name][6] += int(UPS_stats.group('nqdp'))
                    stats['UPS'][channel_name][7] += int(UPS_stats.group('nini'))
                    stats['UPS'][channel_name][8] += int(UPS_stats.group('n100'))
                    stats['UPS'][channel_name][9] += int(UPS_stats.group('n10'))
                except KeyError:
                    stats['UPS'][channel_name] = [int(UPS_stats.group('ntot')),
                      int(UPS_stats.group('nsun')),int(UPS_stats.group('nsps')),
                      int(UPS_stats.group('nups')),int(UPS_stats.group('neps')),
                      int(UPS_stats.group('nddp')),int(UPS_stats.group('nqdp')),
                      int(UPS_stats.group('nini')),int(UPS_stats.group('n100')),
                      int(UPS_stats.group('n10')),[0]*10]
        debug_msg = ""
        if len(stats['UPS'].keys())>0:
            nTotPS  = sum([chan[0] for chan in stats['UPS'].values()],0)
            nTotsun = sum([chan[1] for chan in stats['UPS'].values()],0)
            nTotsps = sum([chan[2] for chan in stats['UPS'].values()],0)
            nTotups = sum([chan[3] for chan in stats['UPS'].values()],0)
            nToteps = sum([chan[4] for chan in stats['UPS'].values()],0)
            nTotddp = sum([chan[5] for chan in stats['UPS'].values()],0)
            nTotqdp = sum([chan[6] for chan in stats['UPS'].values()],0)
            nTotini = sum([chan[7] for chan in stats['UPS'].values()],0)
            nTot100 = sum([chan[8] for chan in stats['UPS'].values()],0)
            nTot10  = sum([chan[9] for chan in stats['UPS'].values()],0)
            nTot1  = [sum([chan[10][i] for chan in stats['UPS'].values()],0) \
                                                             for i in range(10)]
            UPSfracs = [(chan[0] , 0.0 if chan[1][0]==0 else \
                 float(chan[1][4]*100)/chan[1][0]) for chan in stats['UPS'].items()]
            maxUPS = max(UPSfracs, key = lambda w: w[1])

            tmpStr = ""
            tmpStr += '\n  Number of loop ME evaluations (by MadLoop): %d'%nTotPS
            tmpStr += '\n    Stability unknown:                   %d'%nTotsun
            tmpStr += '\n    Stable PS point:                     %d'%nTotsps
            tmpStr += '\n    Unstable PS point (and rescued):     %d'%nTotups
            tmpStr += '\n    Unstable PS point (and not rescued): %d'%nToteps
            tmpStr += '\n    Only double precision used:          %d'%nTotddp
            tmpStr += '\n    Quadruple precision used:            %d'%nTotqdp
            tmpStr += '\n    Initialization phase-space points:   %d'%nTotini
            tmpStr += '\n    Reduction methods used:'
            red_methods = [(unit_code_meaning[i],nTot1[i]) for i in \
                                         unit_code_meaning.keys() if nTot1[i]>0]
            for method, n in sorted(red_methods, key= lambda l: l[1], reverse=True):
                tmpStr += '\n      > %s%s%s'%(method,' '*(33-len(method)),n)                
            if nTot100 != 0:
                debug_msg += '\n  Unknown return code (100):             %d'%nTot100
            if nTot10 != 0:
                debug_msg += '\n  Unknown return code (10):              %d'%nTot10
            nUnknownUnit = sum(nTot1[u] for u in range(10) if u \
                                                not in unit_code_meaning.keys())
            if nUnknownUnit != 0:
                debug_msg += '\n  Unknown return code (1):               %d'\
                                                                   %nUnknownUnit

            if maxUPS[1]>0.001:
                message += tmpStr
                message += '\n  Total number of unstable PS point detected:'+\
                                 ' %d (%4.2f%%)'%(nToteps,float(100*nToteps)/nTotPS)
                message += '\n    Maximum fraction of UPS points in '+\
                          'channel %s (%4.2f%%)'%maxUPS
                message += '\n    Please report this to the authors while '+\
                                                                'providing the file'
                message += '\n    %s'%str(pjoin(os.path.dirname(self.me_dir),
                                                               maxUPS[0],'UPS.log'))
            else:
                debug_msg += tmpStr

    
        # ====================================================
        # == aMC@NLO virtual integration optimization stats ==
        # ====================================================
    
        virt_tricks_finder = re.compile(
          r"accumulated results Virtual ratio\s*=\s*-?(?P<v_ratio>[\d\+-Eed\.]*)"+\
            r"\s*\+/-\s*-?[\d\+-Eed\.]*\s*\(\s*-?(?P<v_ratio_err>[\d\+-Eed\.]*)\s*\%\)\s*\n"+\
          r"accumulated results ABS virtual\s*=\s*-?(?P<v_abs_contr>[\d\+-Eed\.]*)"+\
            r"\s*\+/-\s*-?[\d\+-Eed\.]*\s*\(\s*-?(?P<v_abs_contr_err>[\d\+-Eed\.]*)\s*\%\)")
    
        virt_frac_finder = re.compile(r"update virtual fraction to\s*:\s*"+\
                     "-?(?P<v_frac>[\d\+-Eed\.]*)\s*-?(?P<v_average>[\d\+-Eed\.]*)")
        
        channel_contr_finder = re.compile(r"Final result \[ABS\]\s*:\s*-?(?P<v_contr>[\d\+-Eed\.]*)")
        
        channel_contr_list = {}
        for gv_log in log_GV_files:
            logfile=open(gv_log,'r')
            log = logfile.read()
            logfile.close()
            channel_name = '/'.join(gv_log.split('/')[-3:-1])
            vf_stats = None
            for vf_stats in re.finditer(virt_frac_finder, log):
                pass
            if not vf_stats is None:
                v_frac = float(vf_stats.group('v_frac'))
                v_average = float(vf_stats.group('v_average'))
                try:
                    if v_frac < stats['virt_stats']['v_frac_min'][0]:
                        stats['virt_stats']['v_frac_min']=(v_frac,channel_name)
                    if v_frac > stats['virt_stats']['v_frac_max'][0]:
                        stats['virt_stats']['v_frac_max']=(v_frac,channel_name)
                    stats['virt_stats']['v_frac_avg'][0] += v_frac
                    stats['virt_stats']['v_frac_avg'][1] += 1
                except KeyError:
                    stats['virt_stats']['v_frac_min']=[v_frac,channel_name]
                    stats['virt_stats']['v_frac_max']=[v_frac,channel_name]
                    stats['virt_stats']['v_frac_avg']=[v_frac,1]


            ccontr_stats = None
            for ccontr_stats in re.finditer(channel_contr_finder, log):
                pass
            if not ccontr_stats is None:
                contrib = float(ccontr_stats.group('v_contr'))
                try:
                    if contrib>channel_contr_list[channel_name]:
                        channel_contr_list[channel_name]=contrib
                except KeyError:
                    channel_contr_list[channel_name]=contrib
                
                
        # Now build the list of relevant virt log files to look for the maxima
        # of virt fractions and such.
        average_contrib = 0.0
        for value in channel_contr_list.values():
            average_contrib += value
        if len(channel_contr_list.values()) !=0:
            average_contrib = average_contrib / len(channel_contr_list.values())
        
        relevant_log_GV_files = []
        excluded_channels = set([])
        all_channels = set([])
        for log_file in log_GV_files:
            channel_name = '/'.join(log_file.split('/')[-3:-1])
            all_channels.add(channel_name)
            try:
                if channel_contr_list[channel_name] > (0.1*average_contrib):
                    relevant_log_GV_files.append(log_file)
                else:
                    excluded_channels.add(channel_name)
            except KeyError:
                    relevant_log_GV_files.append(log_file)
        
        # Now we want to use the latest occurence of accumulated result in the log file
        for gv_log in relevant_log_GV_files:
            logfile=open(gv_log,'r')
            log = logfile.read()
            logfile.close()
            channel_name = '/'.join(gv_log.split('/')[-3:-1])
            
            vt_stats = None
            for vt_stats in re.finditer(virt_tricks_finder, log):
                pass
            if not vt_stats is None:
                vt_stats_group = vt_stats.groupdict()
                v_ratio = float(vt_stats.group('v_ratio'))
                v_ratio_err = float(vt_stats.group('v_ratio_err'))
                v_contr = float(vt_stats.group('v_abs_contr'))
                v_contr_err = float(vt_stats.group('v_abs_contr_err'))
                try:
                    if v_ratio < stats['virt_stats']['v_ratio_min'][0]:
                        stats['virt_stats']['v_ratio_min']=(v_ratio,channel_name)
                    if v_ratio > stats['virt_stats']['v_ratio_max'][0]:
                        stats['virt_stats']['v_ratio_max']=(v_ratio,channel_name)
                    if v_ratio < stats['virt_stats']['v_ratio_err_min'][0]:
                        stats['virt_stats']['v_ratio_err_min']=(v_ratio_err,channel_name)
                    if v_ratio > stats['virt_stats']['v_ratio_err_max'][0]:
                        stats['virt_stats']['v_ratio_err_max']=(v_ratio_err,channel_name)
                    if v_contr < stats['virt_stats']['v_contr_min'][0]:
                        stats['virt_stats']['v_contr_min']=(v_contr,channel_name)
                    if v_contr > stats['virt_stats']['v_contr_max'][0]:
                        stats['virt_stats']['v_contr_max']=(v_contr,channel_name)
                    if v_contr_err < stats['virt_stats']['v_contr_err_min'][0]:
                        stats['virt_stats']['v_contr_err_min']=(v_contr_err,channel_name)
                    if v_contr_err > stats['virt_stats']['v_contr_err_max'][0]:
                        stats['virt_stats']['v_contr_err_max']=(v_contr_err,channel_name)
                except KeyError:
                    stats['virt_stats']['v_ratio_min']=[v_ratio,channel_name]
                    stats['virt_stats']['v_ratio_max']=[v_ratio,channel_name]
                    stats['virt_stats']['v_ratio_err_min']=[v_ratio_err,channel_name]
                    stats['virt_stats']['v_ratio_err_max']=[v_ratio_err,channel_name]
                    stats['virt_stats']['v_contr_min']=[v_contr,channel_name]
                    stats['virt_stats']['v_contr_max']=[v_contr,channel_name]
                    stats['virt_stats']['v_contr_err_min']=[v_contr_err,channel_name]
                    stats['virt_stats']['v_contr_err_max']=[v_contr_err,channel_name]
        
            vf_stats = None
            for vf_stats in re.finditer(virt_frac_finder, log):
                pass
            if not vf_stats is None:
                v_frac = float(vf_stats.group('v_frac'))
                v_average = float(vf_stats.group('v_average'))
                try:
                    if v_average < stats['virt_stats']['v_average_min'][0]:
                        stats['virt_stats']['v_average_min']=(v_average,channel_name)
                    if v_average > stats['virt_stats']['v_average_max'][0]:
                        stats['virt_stats']['v_average_max']=(v_average,channel_name)
                    stats['virt_stats']['v_average_avg'][0] += v_average
                    stats['virt_stats']['v_average_avg'][1] += 1
                except KeyError:
                    stats['virt_stats']['v_average_min']=[v_average,channel_name]
                    stats['virt_stats']['v_average_max']=[v_average,channel_name]
                    stats['virt_stats']['v_average_avg']=[v_average,1]
        
        try:
            debug_msg += '\n\n  Statistics on virtual integration optimization : '
            
            debug_msg += '\n    Maximum virt fraction computed         %.3f (%s)'\
                                       %tuple(stats['virt_stats']['v_frac_max'])
            debug_msg += '\n    Minimum virt fraction computed         %.3f (%s)'\
                                       %tuple(stats['virt_stats']['v_frac_min'])
            debug_msg += '\n    Average virt fraction computed         %.3f'\
              %float(stats['virt_stats']['v_frac_avg'][0]/float(stats['virt_stats']['v_frac_avg'][1]))
            debug_msg += '\n  Stats below exclude negligible channels (%d excluded out of %d)'%\
                 (len(excluded_channels),len(all_channels))
            debug_msg += '\n    Maximum virt ratio used                %.2f (%s)'\
                                    %tuple(stats['virt_stats']['v_average_max'])          
            debug_msg += '\n    Maximum virt ratio found from grids    %.2f (%s)'\
                                     %tuple(stats['virt_stats']['v_ratio_max'])
            tmpStr = '\n    Max. MC err. on virt ratio from grids  %.1f %% (%s)'\
                                  %tuple(stats['virt_stats']['v_ratio_err_max'])
            debug_msg += tmpStr
            # After all it was decided that it is better not to alarm the user unecessarily
            # with such printout of the statistics.
#            if stats['virt_stats']['v_ratio_err_max'][0]>100.0 or \
#                                stats['virt_stats']['v_ratio_err_max'][0]>100.0:
#                message += "\n  Suspiciously large MC error in :"
#            if stats['virt_stats']['v_ratio_err_max'][0]>100.0:
#                message += tmpStr

            tmpStr = '\n    Maximum MC error on abs virt           %.1f %% (%s)'\
                                  %tuple(stats['virt_stats']['v_contr_err_max'])
            debug_msg += tmpStr
#            if stats['virt_stats']['v_contr_err_max'][0]>100.0:
#                message += tmpStr
            

        except KeyError:
            debug_msg += '\n  Could not find statistics on the integration optimization. '
    
        # =======================================
        # == aMC@NLO timing profile statistics ==
        # =======================================
    
        timing_stat_finder = re.compile(r"\s*Time spent in\s*(?P<name>\w*)\s*:\s*"+\
                     "(?P<time>[\d\+-Eed\.]*)\s*")

        for logf in log_GV_files:
            logfile=open(logf,'r')
            log = logfile.read()
            logfile.close()
            channel_name = '/'.join(logf.split('/')[-3:-1])
            mint = re.search(mint_search,logf)
            if not mint is None:
               channel_name =   channel_name+' [step %s]'%mint.group('ID')

            for time_stats in re.finditer(timing_stat_finder, log):
                try:
                    stats['timings'][time_stats.group('name')][channel_name]+=\
                                                 float(time_stats.group('time'))
                except KeyError:
                    if time_stats.group('name') not in stats['timings'].keys():
                        stats['timings'][time_stats.group('name')] = {}
                    stats['timings'][time_stats.group('name')][channel_name]=\
                                                 float(time_stats.group('time'))
        
        # useful inline function
        Tstr = lambda secs: str(datetime.timedelta(seconds=int(secs)))
        try:
            totTimeList = [(time, chan) for chan, time in \
                                              stats['timings']['Total'].items()]
        except KeyError:
            totTimeList = []

        totTimeList.sort()
        if len(totTimeList)>0:
            debug_msg += '\n\n  Inclusive timing profile :'
            debug_msg += '\n    Overall slowest channel          %s (%s)'%\
                                     (Tstr(totTimeList[-1][0]),totTimeList[-1][1])
            debug_msg += '\n    Average channel running time     %s'%\
                       Tstr(sum([el[0] for el in totTimeList])/len(totTimeList))
            debug_msg += '\n    Aggregated total running time    %s'%\
                                        Tstr(sum([el[0] for el in totTimeList]))       
        else:            
            debug_msg += '\n\n  Inclusive timing profile non available.'
        
        sorted_keys = sorted(stats['timings'].keys(), key= lambda stat: \
                              sum(stats['timings'][stat].values()), reverse=True)
        for name in sorted_keys:
            if name=='Total':
                continue
            if sum(stats['timings'][name].values())<=0.0:
                debug_msg += '\n  Zero time record for %s.'%name
                continue
            try:
                TimeList = [((100.0*time/stats['timings']['Total'][chan]), 
                     chan) for chan, time in stats['timings'][name].items()]
            except KeyError, ZeroDivisionError:
                debug_msg += '\n\n  Timing profile for %s unavailable.'%name
                continue
            TimeList.sort()
            debug_msg += '\n  Timing profile for <%s> :'%name
            try:
                debug_msg += '\n    Overall fraction of time         %.3f %%'%\
                       float((100.0*(sum(stats['timings'][name].values())/
                                      sum(stats['timings']['Total'].values()))))
            except KeyError, ZeroDivisionError:
                debug_msg += '\n    Overall fraction of time unavailable.'
            debug_msg += '\n    Largest fraction of time         %.3f %% (%s)'%\
                                             (TimeList[-1][0],TimeList[-1][1])
            debug_msg += '\n    Smallest fraction of time        %.3f %% (%s)'%\
                                             (TimeList[0][0],TimeList[0][1])

        # =============================     
        # == log file eror detection ==
        # =============================
        
        # Find the number of potential errors found in all log files
        # This re is a simple match on a case-insensitve 'error' but there is 
        # also some veto added for excluding the sentence 
        #  "See Section 6 of paper for error calculation."
        # which appear in the header of lhapdf in the logs.
        err_finder = re.compile(\
             r"(?<!of\spaper\sfor\s)\bERROR\b(?!\scalculation\.)",re.IGNORECASE)
        for log in all_log_files:
            logfile=open(log,'r')
            nErrors = len(re.findall(err_finder, logfile.read()))
            logfile.close()
            if nErrors != 0:
                stats['Errors'].append((str(log),nErrors))
         
        nErrors = sum([err[1] for err in stats['Errors']],0)
        if nErrors != 0:
            debug_msg += '\n      WARNING:: A total of %d error%s ha%s been '\
              %(nErrors,'s' if nErrors>1 else '','ve' if nErrors>1 else 's')+\
              'found in the following log file%s:'%('s' if \
                                                 len(stats['Errors'])>1 else '')
            for error in stats['Errors'][:3]:
                log_name = '/'.join(error[0].split('/')[-5:])
                debug_msg += '\n       > %d error%s in %s'%\
                                   (error[1],'s' if error[1]>1 else '',log_name)
            if len(stats['Errors'])>3:
                nRemainingErrors = sum([err[1] for err in stats['Errors']][3:],0)
                nRemainingLogs = len(stats['Errors'])-3
                debug_msg += '\n      And another %d error%s in %d other log file%s'%\
                           (nRemainingErrors, 's' if nRemainingErrors>1 else '',
                               nRemainingLogs, 's ' if nRemainingLogs>1 else '')
                           
        return message, debug_msg


    def reweight_and_collect_events(self, options, mode, nevents, event_norm):
        """this function calls the reweighting routines and creates the event file in the 
        Event dir. Return the name of the event file created
        """
        scale_pdf_info={}
        if (self.run_card['reweight_scale'] == '.true.' or self.run_card['reweight_PDF'] == '.true.') :
            scale_pdf_info = self.run_reweight(options['reweightonly'])

        self.update_status('Collecting events', level='parton', update_results=True)
        misc.compile(['collect_events'], 
                    cwd=pjoin(self.me_dir, 'SubProcesses'))
        p = misc.Popen(['./collect_events'], cwd=pjoin(self.me_dir, 'SubProcesses'),
                stdin=subprocess.PIPE, 
                stdout=open(pjoin(self.me_dir, 'collect_events.log'), 'w'))
        if event_norm.lower() == 'sum':
            p.communicate(input = '1\n')
        elif event_norm.lower() == 'unity':
            p.communicate(input = '3\n')
        else:
            p.communicate(input = '2\n')

        #get filename from collect events
        filename = open(pjoin(self.me_dir, 'collect_events.log')).read().split()[-1]

        if not os.path.exists(pjoin(self.me_dir, 'SubProcesses', filename)):
            raise aMCatNLOError('An error occurred during event generation. ' + \
                    'The event file has not been created. Check collect_events.log')
        evt_file = pjoin(self.me_dir, 'Events', self.run_name, 'events.lhe.gz')
        misc.gzip(pjoin(self.me_dir, 'SubProcesses', filename), stdout=evt_file)
        if not options['reweightonly']:
            self.print_summary(options, 2, mode, scale_pdf_info)
        logger.info('The %s file has been generated.\n' % (evt_file))
        self.results.add_detail('nb_event', nevents)
        self.update_status('Events generated', level='parton', update_results=True)
        return evt_file[:-3]


    def run_mcatnlo(self, evt_file):
        """runs mcatnlo on the generated event file, to produce showered-events
        """
        logger.info('Preparing MCatNLO run')
        try:     
            misc.gunzip(evt_file)
        except Exception:
            pass

        self.banner = banner_mod.Banner(evt_file)
        shower = self.banner.get_detail('run_card', 'parton_shower').upper()

        #check that the number of split event files divides the number of
        # events, otherwise set it to 1
        if int(int(self.banner.get_detail('run_card', 'nevents')) / \
                self.shower_card['nsplit_jobs']) * self.shower_card['nsplit_jobs'] \
                != int(self.banner.get_detail('run_card', 'nevents')):
            logger.warning(\
                'nsplit_jobs in the shower card is not a divisor of the number of events.\n' + \
                'Setting it to 1.')
            self.shower_card['nsplit_jobs'] = 1

        # don't split jobs if the user asks to shower only a part of the events
        if self.shower_card['nevents'] > 0 and \
           self.shower_card['nevents'] < int(self.banner.get_detail('run_card', 'nevents')) and \
           self.shower_card['nsplit_jobs'] != 1:
            logger.warning(\
                'Only a part of the events will be showered.\n' + \
                'Setting nsplit_jobs in the shower_card to 1.')
            self.shower_card['nsplit_jobs'] = 1

        self.banner_to_mcatnlo(evt_file)

        # if fastjet has to be linked (in extralibs) then
        # add lib /include dirs for fastjet if fastjet-config is present on the
        # system, otherwise add fjcore to the files to combine
        if 'fastjet' in self.shower_card['extralibs']:
            #first, check that stdc++ is also linked
            if not 'stdc++' in self.shower_card['extralibs']:
                logger.warning('Linking FastJet: adding stdc++ to EXTRALIBS')
                self.shower_card['extralibs'] += ' stdc++'
            # then check if options[fastjet] corresponds to a valid fj installation
            try:
                #this is for a complete fj installation
                p = subprocess.Popen([self.options['fastjet'], '--prefix'], \
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                output, error = p.communicate()
                #remove the line break from output (last character)
                output = output[:-1]
                # add lib/include paths
                if not pjoin(output, 'lib') in self.shower_card['extrapaths']:
                    logger.warning('Linking FastJet: updating EXTRAPATHS')
                    self.shower_card['extrapaths'] += ' ' + pjoin(output, 'lib')
                if not pjoin(output, 'include') in self.shower_card['includepaths']:
                    logger.warning('Linking FastJet: updating INCLUDEPATHS')
                    self.shower_card['includepaths'] += ' ' + pjoin(output, 'include')
                # to be changed in the fortran wrapper
                include_line = '#include "fastjet/ClusterSequence.hh"//INCLUDE_FJ' 
                namespace_line = 'namespace fj = fastjet;//NAMESPACE_FJ'
            except Exception:
                logger.warning('Linking FastJet: using fjcore')
                # this is for FJcore, so no FJ library has to be linked
                self.shower_card['extralibs'] = self.shower_card['extralibs'].replace('fastjet', '')
                if not 'fjcore.o' in self.shower_card['analyse']:
                    self.shower_card['analyse'] += ' fjcore.o'
                # to be changed in the fortran wrapper
                include_line = '#include "fjcore.hh"//INCLUDE_FJ' 
                namespace_line = 'namespace fj = fjcore;//NAMESPACE_FJ'
            # change the fortran wrapper with the correct namespaces/include
            fjwrapper_lines = open(pjoin(self.me_dir, 'MCatNLO', 'srcCommon', 'myfastjetfortran.cc')).read().split('\n')
            for line in fjwrapper_lines:
                if '//INCLUDE_FJ' in line:
                    fjwrapper_lines[fjwrapper_lines.index(line)] = include_line
                if '//NAMESPACE_FJ' in line:
                    fjwrapper_lines[fjwrapper_lines.index(line)] = namespace_line
            open(pjoin(self.me_dir, 'MCatNLO', 'srcCommon', 'myfastjetfortran.cc'), 'w').write(\
                    '\n'.join(fjwrapper_lines) + '\n')

        extrapaths = self.shower_card['extrapaths'].split()

        # check that the path needed by HW++ and PY8 are set if one uses these shower
        if shower in ['HERWIGPP', 'PYTHIA8']:
            path_dict = {'HERWIGPP': ['hepmc_path',
                                      'thepeg_path',
                                      'hwpp_path'],
                         'PYTHIA8': ['pythia8_path']}

            if not all([self.options[ppath] for ppath in path_dict[shower]]):
                raise aMCatNLOError('Some paths are missing in the configuration file.\n' + \
                        ('Please make sure you have set these variables: %s' % ', '.join(path_dict[shower])))

        if shower == 'HERWIGPP':
            extrapaths.append(pjoin(self.options['hepmc_path'], 'lib'))

        if shower == 'PYTHIA8' and not os.path.exists(pjoin(self.options['pythia8_path'], 'xmldoc')):
            extrapaths.append(pjoin(self.options['pythia8_path'], 'lib'))

        if 'LD_LIBRARY_PATH' in os.environ.keys():
            ldlibrarypath = os.environ['LD_LIBRARY_PATH']
        else:
            ldlibrarypath = ''
        ldlibrarypath += ':' + ':'.join(extrapaths)
        os.putenv('LD_LIBRARY_PATH', ldlibrarypath)

        shower_card_path = pjoin(self.me_dir, 'MCatNLO', 'shower_card.dat')
        self.shower_card.write_card(shower, shower_card_path)

        mcatnlo_log = pjoin(self.me_dir, 'mcatnlo.log')
        self.update_status('Compiling MCatNLO for %s...' % shower, level='shower') 
        misc.call(['./MCatNLO_MadFKS.inputs'], stdout=open(mcatnlo_log, 'w'),
                    stderr=open(mcatnlo_log, 'w'), 
                    cwd=pjoin(self.me_dir, 'MCatNLO'))

        exe = 'MCATNLO_%s_EXE' % shower
        if not os.path.exists(pjoin(self.me_dir, 'MCatNLO', exe)) and \
            not os.path.exists(pjoin(self.me_dir, 'MCatNLO', 'Pythia8.exe')):
            print open(mcatnlo_log).read()
            raise aMCatNLOError('Compilation failed, check %s for details' % mcatnlo_log)
        logger.info('                     ... done')

        # create an empty dir where to run
        count = 1
        while os.path.isdir(pjoin(self.me_dir, 'MCatNLO', 'RUN_%s_%d' % \
                        (shower, count))):
            count += 1
        rundir = pjoin(self.me_dir, 'MCatNLO', 'RUN_%s_%d' % \
                        (shower, count))
        os.mkdir(rundir)
        files.cp(shower_card_path, rundir)

        #look for the event files (don't resplit if one asks for the 
        # same number of event files as in the previous run)
        event_files = glob.glob(pjoin(self.me_dir, 'Events', self.run_name,
                                            'events_*.lhe'))
        if max(len(event_files), 1) != self.shower_card['nsplit_jobs']:
            logger.info('Cleaning old files and splitting the event file...')
            #clean the old files
            files.rm([f for f in event_files if 'events.lhe' not in f])
            if self.shower_card['nsplit_jobs'] > 1:
                misc.compile(['split_events'], cwd = pjoin(self.me_dir, 'Utilities'))
                p = misc.Popen([pjoin(self.me_dir, 'Utilities', 'split_events')],
                                stdin=subprocess.PIPE,
                                stdout=open(pjoin(self.me_dir, 'Events', self.run_name, 'split_events.log'), 'w'),
                                cwd=pjoin(self.me_dir, 'Events', self.run_name))
                p.communicate(input = 'events.lhe\n%d\n' % self.shower_card['nsplit_jobs'])
                logger.info('Splitting done.')
            event_files = glob.glob(pjoin(self.me_dir, 'Events', self.run_name,
                                            'events_*.lhe'))

        event_files.sort()

        self.update_status('Showering events...', level='shower')
        logger.info('(Running in %s)' % rundir)
        if shower != 'PYTHIA8':
            files.mv(pjoin(self.me_dir, 'MCatNLO', exe), rundir)
            files.mv(pjoin(self.me_dir, 'MCatNLO', 'MCATNLO_%s_input' % shower), rundir)
        else:
        # special treatment for pythia8
            files.mv(pjoin(self.me_dir, 'MCatNLO', 'Pythia8.cmd'), rundir)
            files.mv(pjoin(self.me_dir, 'MCatNLO', 'Pythia8.exe'), rundir)
            if os.path.exists(pjoin(self.options['pythia8_path'], 'xmldoc')):
                files.ln(pjoin(self.options['pythia8_path'], 'examples', 'config.sh'), rundir)
                files.ln(pjoin(self.options['pythia8_path'], 'xmldoc'), rundir)
            else:
                files.ln(pjoin(self.options['pythia8_path'], 'share/Pythia8/xmldoc'), rundir)
        #link the hwpp exe in the rundir
        if shower == 'HERWIGPP':
            try:
                files.ln(pjoin(self.options['hwpp_path'], 'bin', 'Herwig++'), rundir)
            except Exception:
                raise aMCatNLOError('The Herwig++ path set in the configuration file is not valid.')

            if os.path.exists(pjoin(self.me_dir, 'MCatNLO', 'HWPPAnalyzer', 'HepMCFortran.so')):
                files.cp(pjoin(self.me_dir, 'MCatNLO', 'HWPPAnalyzer', 'HepMCFortran.so'), rundir)

        files.ln(evt_file, rundir, 'events.lhe')
        for i, f in enumerate(event_files):
            files.ln(f, rundir,'events_%d.lhe' % (i + 1))

        if not self.shower_card['analyse']:
            # an hep/hepmc file as output
            out_id = 'HEP'
        else:
            # one or more .top file(s) as output
            out_id = 'TOP'

        # write the executable
        open(pjoin(rundir, 'shower.sh'), 'w').write(\
                open(pjoin(self.me_dir, 'MCatNLO', 'shower_template.sh')).read() \
                % {'extralibs': ':'.join(extrapaths)})
        subprocess.call(['chmod', '+x', pjoin(rundir, 'shower.sh')])

        if event_files:
            arg_list = [[shower, out_id, self.run_name, '%d' % (i + 1)] \
                    for i in range(len(event_files))]
        else:
            arg_list = [[shower, out_id, self.run_name]]

        self.run_all({rundir: 'shower.sh'}, arg_list, 'shower')
        self.njobs = 1
        self.wait_for_complete('shower')

        # now collect the results
        message = ''
        warning = ''
        to_gzip = [evt_file]
        if out_id == 'HEP':
            #copy the showered stdhep/hepmc file back in events
            if shower in ['PYTHIA8', 'HERWIGPP']:
                hep_format = 'HEPMC'
                ext = 'hepmc'
            else:
                hep_format = 'StdHEP'
                ext = 'hep'

            hep_file = '%s_%s_0.%s.gz' % \
                    (pjoin(os.path.dirname(evt_file), 'events'), shower, ext)
            count = 0

            # find the first available name for the output:
            # check existing results with or without event splitting
            while os.path.exists(hep_file) or \
                  os.path.exists(hep_file.replace('.%s.gz' % ext, '__1.%s.gz' % ext)) :
                count +=1
                hep_file = '%s_%s_%d.%s.gz' % \
                    (pjoin(os.path.dirname(evt_file), 'events'), shower, count, ext)

            try:
                if self.shower_card['nsplit_jobs'] == 1:
                    files.mv(os.path.join(rundir, 'events.%s.gz' % ext), hep_file) 
                    message = ('The file %s has been generated. \nIt contains showered' + \
                     ' and hadronized events in the %s format obtained' + \
                     ' showering the parton-level event file %s.gz with %s') % \
                     (hep_file, hep_format, evt_file, shower)
                else:
                    hep_list = []
                    for i in range(self.shower_card['nsplit_jobs']):
                        hep_list.append(hep_file.replace('.%s.gz' % ext, '__%d.%s.gz' % (i + 1, ext)))
                        files.mv(os.path.join(rundir, 'events_%d.%s.gz' % (i + 1, ext)), hep_list[-1]) 
                    message = ('The following files have been generated:\n  %s\nThey contain showered' + \
                     ' and hadronized events in the %s format obtained' + \
                     ' showering the (split) parton-level event file %s.gz with %s') % \
                     ('\n  '.join(hep_list), hep_format, evt_file, shower)

            except OSError, IOError:
                raise aMCatNLOError('No file has been generated, an error occurred.'+\
             ' More information in %s' % pjoin(os.getcwd(), 'amcatnlo_run.log'))

            # run the plot creation in a secure way
            if hep_format == 'StdHEP':
                try:
                    self.do_plot('%s -f' % self.run_name)
                except Exception, error:
                    logger.info("Fail to make the plot. Continue...")
                    pass

        elif out_id == 'TOP':
            #copy the topdrawer file(s) back in events
            topfiles = []
            top_tars = [tarfile.TarFile(f) for f in glob.glob(pjoin(rundir, 'topfile*.tar'))]
            for top_tar in top_tars:
                topfiles.extend(top_tar.getnames())

            # safety check
            if len(top_tars) != self.shower_card['nsplit_jobs']:
                raise aMCatNLOError('%d job(s) expected, %d file(s) found' % \
                                     (self.shower_card['nsplit_jobs'], len(top_tars)))

            # find the first available name for the output:
            # check existing results with or without event splitting
            filename = 'plot_%s_%d_' % (shower, 1)
            count = 1
            while os.path.exists(pjoin(self.me_dir, 'Events', 
                      self.run_name, '%s0.top' % filename)) or \
                  os.path.exists(pjoin(self.me_dir, 'Events', 
                      self.run_name, '%s0__1.top' % filename)):
                count += 1
                filename = 'plot_%s_%d_' % (shower, count)

            if not topfiles:
                # if no topfiles are found just warn the user
                waarning = 'No .top file has been generated. For the results of your ' +\
                               'run, please check inside %s' % rundir

            elif self.shower_card['nsplit_jobs'] == 1:
                # only one job for the shower
                top_tars[0].extractall(path = rundir) 
                plotfiles = [] 
                for i, file in enumerate(topfiles):
                    plotfile = pjoin(self.me_dir, 'Events', self.run_name, 
                              '%s%d.top' % (filename, i))
                    files.mv(pjoin(rundir, file), plotfile) 
                    plotfiles.append(plotfile)

                ffiles = 'files'
                have = 'have'
                if len(plotfiles) == 1:
                    ffiles = 'file'
                    have = 'has'

                message = ('The %s %s %s been generated, with histograms in the' + \
                        ' TopDrawer format, obtained by showering the parton-level' + \
                        ' file %s.gz with %s.') % (ffiles, ', '.join(plotfiles), have, \
                        evt_file, shower)
            else:
                # many jobs for the shower have been run
                topfiles_set = set(topfiles)
                plotfiles = [] 
                for j, top_tar in enumerate(top_tars):
                    top_tar.extractall(path = rundir) 
                    for i, file in enumerate(topfiles_set):
                        plotfile = pjoin(self.me_dir, 'Events', self.run_name, 
                                  '%s%d__%d.top' % (filename, i, j + 1))
                        files.mv(pjoin(rundir, file), plotfile) 
                        plotfiles.append(plotfile)

                # check if the user asked to combine the .top into a single file
                if self.shower_card['combine_td']:
                    misc.compile(['sum_plots'], cwd = pjoin(self.me_dir, 'Utilities'))

                    if self.banner.get('run_card', 'event_norm').lower() == 'sum':
                        norm = 1.
                    elif self.banner.get('run_card', 'event_norm').lower() == 'average':
                        norm = 1./float(self.shower_card['nsplit_jobs'])

                    plotfiles = []
                    for i, file in enumerate(topfiles_set):
                        filelist = ['%s%d__%d.top' % (filename, i, j + 1) \
                                    for j in range(self.shower_card['nsplit_jobs'])]
                        infile="%d\n%s\n%s\n" % \
                                (self.shower_card['nsplit_jobs'],
                                 '\n'.join(filelist),
                                 '\n'.join([str(norm)] * self.shower_card['nsplit_jobs']))

                        p = misc.Popen([pjoin(self.me_dir, 'Utilities', 'sum_plots')],
                                        stdin=subprocess.PIPE,
                                        stdout=os.open(os.devnull, os.O_RDWR), 
                                        cwd=pjoin(self.me_dir, 'Events', self.run_name))
                        p.communicate(input = infile)
                        files.mv(pjoin(self.me_dir, 'Events', self.run_name, 'sum.top'),
                                 pjoin(self.me_dir, 'Events', self.run_name, '%s%d.top' % (filename, i)))
                        plotfiles.append(pjoin(self.me_dir, 'Events', self.run_name, '%s%d.top' % (filename, i)))
                        tar = tarfile.open(
                                pjoin(self.me_dir, 'Events', self.run_name, '%s%d.tar.gz' % (filename, i)), 'w:gz')
                        for f in filelist:
                            tar.add(pjoin(self.me_dir, 'Events', self.run_name, f), arcname=f)
                        files.rm([pjoin(self.me_dir, 'Events', self.run_name, f) for f in filelist])

                    tar.close()

                    ffiles = 'files'
                    have = 'have'
                    if len(plotfiles) == 1:
                        ffiles = 'file'
                        have = 'has'

                    message = ('The %s %s %s been generated, with histograms in the' + \
                            ' TopDrawer format, obtained by showering the parton-level' + \
                            ' file %s.gz with %s.\n' + \
                            'The files from the different shower ' + \
                            'jobs (before combining them) can be found inside %s.') % \
                            (ffiles, ', '.join(plotfiles), have, \
                             evt_file, shower, 
                             ', '.join([f.replace('top', 'tar.gz') for f in plotfiles]))

                else:
                    message = ('The following files have been generated:\n  %s\n' + \
                            'They contain histograms in the' + \
                            ' TopDrawer format, obtained by showering the parton-level' + \
                            ' file %s.gz with %s.') % ('\n  '.join(plotfiles), \
                            evt_file, shower)
                
        # Now arxiv the shower card used if RunMaterial is present
        run_dir_path = pjoin(rundir, self.run_name)
        if os.path.exists(pjoin(run_dir_path,'RunMaterial.tar.gz')):
            misc.call(['tar','-xzpf','RunMaterial.tar.gz'],cwd=run_dir_path)
            files.cp(pjoin(self.me_dir,'Cards','shower_card.dat'),
               pjoin(run_dir_path,'RunMaterial','shower_card_for_%s_%d.dat'\
                                                          %(shower, count)))
            misc.call(['tar','-czpf','RunMaterial.tar.gz','RunMaterial'], 
                                                           cwd=run_dir_path)
            shutil.rmtree(pjoin(run_dir_path,'RunMaterial'))
        # end of the run, gzip files and print out the message/warning
        for f in to_gzip:
            misc.gzip(f)
        if message:
            logger.info(message)
        if warning:
            logger.warning(warning)

        self.update_status('Run complete', level='shower', update_results=True)


    ############################################################################
    def set_run_name(self, name, tag=None, level='parton', reload_card=False):
        """define the run name, the run_tag, the banner and the results."""
        
        # when are we force to change the tag new_run:previous run requiring changes
        upgrade_tag = {'parton': ['parton','pythia','pgs','delphes','shower'],
                       'pythia': ['pythia','pgs','delphes'],
                       'shower': ['shower'],
                       'pgs': ['pgs'],
                       'delphes':['delphes'],
                       'plot':[]}
        
        

        if name == self.run_name:        
            if reload_card:
                run_card = pjoin(self.me_dir, 'Cards','run_card.dat')
                self.run_card = banner_mod.RunCardNLO(run_card)

            #check if we need to change the tag
            if tag:
                self.run_card['run_tag'] = tag
                self.run_tag = tag
                self.results.add_run(self.run_name, self.run_card)
            else:
                for tag in upgrade_tag[level]:
                    if getattr(self.results[self.run_name][-1], tag):
                        tag = self.get_available_tag()
                        self.run_card['run_tag'] = tag
                        self.run_tag = tag
                        self.results.add_run(self.run_name, self.run_card)                        
                        break
            return # Nothing to do anymore
        
        # save/clean previous run
        if self.run_name:
            self.store_result()
        # store new name
        self.run_name = name
        
        # Read run_card
        run_card = pjoin(self.me_dir, 'Cards','run_card.dat')
        self.run_card = banner_mod.RunCardNLO(run_card)

        new_tag = False
        # First call for this run -> set the banner
        self.banner = banner_mod.recover_banner(self.results, level, self.run_name, tag)
        if tag:
            self.run_card['run_tag'] = tag
            new_tag = True
        elif not self.run_name in self.results and level =='parton':
            pass # No results yet, so current tag is fine
        elif not self.run_name in self.results:
            #This is only for case when you want to trick the interface
            logger.warning('Trying to run data on unknown run.')
            self.results.add_run(name, self.run_card)
            self.results.update('add run %s' % name, 'all', makehtml=True)
        else:
            for tag in upgrade_tag[level]:
                
                if getattr(self.results[self.run_name][-1], tag):
                    # LEVEL is already define in the last tag -> need to switch tag
                    tag = self.get_available_tag()
                    self.run_card['run_tag'] = tag
                    new_tag = True
                    break
            if not new_tag:
                # We can add the results to the current run
                tag = self.results[self.run_name][-1]['tag']
                self.run_card['run_tag'] = tag # ensure that run_tag is correct                
             
                    
        if name in self.results and not new_tag:
            self.results.def_current(self.run_name)
        else:
            self.results.add_run(self.run_name, self.run_card)

        self.run_tag = self.run_card['run_tag']

        # Return the tag of the previous run having the required data for this
        # tag/run to working wel.
        if level == 'parton':
            return
        elif level == 'pythia':
            return self.results[self.run_name][0]['tag']
        else:
            for i in range(-1,-len(self.results[self.run_name])-1,-1):
                tagRun = self.results[self.run_name][i]
                if tagRun.pythia:
                    return tagRun['tag']


    def store_result(self):
        """ tar the pythia results. This is done when we are quite sure that 
        the pythia output will not be use anymore """

        if not self.run_name:
            return

        self.results.save()

        if not self.to_store:
            return 
        
        tag = self.run_card['run_tag']
        
        self.to_store = []


    def get_init_dict(self, evt_file):
        """reads the info in the init block and returns them in a dictionary"""
        ev_file = open(evt_file)
        init = ""
        found = False
        while True:
            line = ev_file.readline()
            if "<init>" in line:
                found = True
            elif found and not line.startswith('#'):
                init += line
            if "</init>" in line or "<event>" in line:
                break
        ev_file.close()

#       IDBMUP(1),IDBMUP(2),EBMUP(1),EBMUP(2), PDFGUP(1),PDFGUP(2),
#       PDFSUP(1),PDFSUP(2),IDWTUP,NPRUP
# these are not included (so far) in the init_dict
#       XSECUP(1),XERRUP(1),XMAXUP(1),LPRUP(1)
            
        init_dict = {}
        init_dict['idbmup1'] = int(init.split()[0])
        init_dict['idbmup2'] = int(init.split()[1])
        init_dict['ebmup1'] = float(init.split()[2])
        init_dict['ebmup2'] = float(init.split()[3])
        init_dict['pdfgup1'] = int(init.split()[4])
        init_dict['pdfgup2'] = int(init.split()[5])
        init_dict['pdfsup1'] = int(init.split()[6])
        init_dict['pdfsup2'] = int(init.split()[7])
        init_dict['idwtup'] = int(init.split()[8])
        init_dict['nprup'] = int(init.split()[9])

        return init_dict


    def banner_to_mcatnlo(self, evt_file):
        """creates the mcatnlo input script using the values set in the header of the event_file.
        It also checks if the lhapdf library is used"""
        shower = self.banner.get('run_card', 'parton_shower').upper()
        pdlabel = self.banner.get('run_card', 'pdlabel')
        itry = 0
        nevents = self.shower_card['nevents']
        init_dict = self.get_init_dict(evt_file)

        if nevents < 0 or \
           nevents > int(self.banner.get_detail('run_card', 'nevents')):
            nevents = int(self.banner.get_detail('run_card', 'nevents'))

        nevents = nevents / self.shower_card['nsplit_jobs']

        mcmass_dict = {}
        for line in [l for l in self.banner['montecarlomasses'].split('\n') if l]:
            pdg = int(line.split()[0])
            mass = float(line.split()[1])
            mcmass_dict[pdg] = mass

        content = 'EVPREFIX=%s\n' % pjoin(os.path.split(evt_file)[1])
        content += 'NEVENTS=%d\n' % nevents
        content += 'NEVENTS_TOT=%d\n' % (int(self.banner.get_detail('run_card', 'nevents')) /\
                                             self.shower_card['nsplit_jobs'])
        content += 'MCMODE=%s\n' % shower
        content += 'PDLABEL=%s\n' % pdlabel
        content += 'ALPHAEW=%s\n' % self.banner.get_detail('param_card', 'sminputs', 1).value
        #content += 'PDFSET=%s\n' % self.banner.get_detail('run_card', 'lhaid')
        #content += 'PDFSET=%s\n' % max([init_dict['pdfsup1'],init_dict['pdfsup2']])
        content += 'TMASS=%s\n' % self.banner.get_detail('param_card', 'mass', 6).value
        content += 'TWIDTH=%s\n' % self.banner.get_detail('param_card', 'decay', 6).value
        content += 'ZMASS=%s\n' % self.banner.get_detail('param_card', 'mass', 23).value
        content += 'ZWIDTH=%s\n' % self.banner.get_detail('param_card', 'decay', 23).value
        content += 'WMASS=%s\n' % self.banner.get_detail('param_card', 'mass', 24).value
        content += 'WWIDTH=%s\n' % self.banner.get_detail('param_card', 'decay', 24).value
        try:
            content += 'HGGMASS=%s\n' % self.banner.get_detail('param_card', 'mass', 25).value
            content += 'HGGWIDTH=%s\n' % self.banner.get_detail('param_card', 'decay', 25).value
        except KeyError:
            content += 'HGGMASS=120.\n'
            content += 'HGGWIDTH=0.00575308848\n'
        content += 'beammom1=%s\n' % self.banner.get_detail('run_card', 'ebeam1')
        content += 'beammom2=%s\n' % self.banner.get_detail('run_card', 'ebeam2')
        content += 'BEAM1=%s\n' % self.banner.get_detail('run_card', 'lpp1')
        content += 'BEAM2=%s\n' % self.banner.get_detail('run_card', 'lpp2')
        content += 'DMASS=%s\n' % mcmass_dict[1]
        content += 'UMASS=%s\n' % mcmass_dict[2]
        content += 'SMASS=%s\n' % mcmass_dict[3]
        content += 'CMASS=%s\n' % mcmass_dict[4]
        content += 'BMASS=%s\n' % mcmass_dict[5]
        try:
            content += 'EMASS=%s\n' % mcmass_dict[11]
            content += 'MUMASS=%s\n' % mcmass_dict[13]
            content += 'TAUMASS=%s\n' % mcmass_dict[15]
        except KeyError:
            # this is for backward compatibility
            mcmass_lines = [l for l in \
                    open(pjoin(self.me_dir, 'SubProcesses', 'MCmasses_%s.inc' % shower.upper())
                            ).read().split('\n') if l]
            new_mcmass_dict = {}
            for l in mcmass_lines:
                key, val = l.split('=')
                new_mcmass_dict[key.strip()] = val.replace('d', 'e').strip()
            content += 'EMASS=%s\n' % new_mcmass_dict['mcmass(11)']
            content += 'MUMASS=%s\n' % new_mcmass_dict['mcmass(13)']
            content += 'TAUMASS=%s\n' % new_mcmass_dict['mcmass(15)']

        content += 'GMASS=%s\n' % mcmass_dict[21]
        content += 'EVENT_NORM=%s\n' % self.banner.get_detail('run_card', 'event_norm').lower()
        # check if need to link lhapdf
        if int(self.shower_card['pdfcode']) > 1 or \
            (pdlabel=='lhapdf' and int(self.shower_card['pdfcode'])==1): 
            # Use LHAPDF (should be correctly installed, because
            # either events were already generated with them, or the
            # user explicitly gives an LHAPDF number in the
            # shower_card).
            self.link_lhapdf(pjoin(self.me_dir, 'lib'))
            lhapdfpath = subprocess.Popen([self.options['lhapdf'], '--prefix'], 
                                          stdout = subprocess.PIPE).stdout.read().strip()
            content += 'LHAPDFPATH=%s\n' % lhapdfpath
            pdfsetsdir = self.get_lhapdf_pdfsetsdir()
            if self.shower_card['pdfcode']==1:
                lhaid_list = [max([init_dict['pdfsup1'],init_dict['pdfsup2']])]
                content += 'PDFCODE=%s\n' % max([init_dict['pdfsup1'],init_dict['pdfsup2']])
            else:
                lhaid_list = [abs(int(self.shower_card['pdfcode']))]
                content += 'PDFCODE=%s\n' % self.shower_card['pdfcode']
            self.copy_lhapdf_set(lhaid_list, pdfsetsdir)
        elif int(self.shower_card['pdfcode'])==1:
            # Try to use LHAPDF because user wants to use the same PDF
            # as was used for the event generation. However, for the
            # event generation, LHAPDF was not used, so non-trivial to
            # see if if LHAPDF is available with the corresponding PDF
            # set. If not found, give a warning and use build-in PDF
            # set instead.
            try:
                lhapdfpath = subprocess.Popen([self.options['lhapdf'], '--prefix'], 
                                              stdout = subprocess.PIPE).stdout.read().strip()
                self.link_lhapdf(pjoin(self.me_dir, 'lib'))
                content += 'LHAPDFPATH=%s\n' % lhapdfpath
                pdfsetsdir = self.get_lhapdf_pdfsetsdir()
                lhaid_list = [max([init_dict['pdfsup1'],init_dict['pdfsup2']])]
                content += 'PDFCODE=%s\n' % max([init_dict['pdfsup1'],init_dict['pdfsup2']])
                self.copy_lhapdf_set(lhaid_list, pdfsetsdir)
            except Exception:
                logger.warning('Trying to shower events using the same PDF in the shower as used in the generation'+\
                                   ' of the events using LHAPDF. However, no valid LHAPDF installation found with the'+\
                                   ' needed PDF set. Will use default internal PDF for the shower instead. To use the'+\
                                   ' same set as was used in the event generation install LHAPDF and set the path using'+\
                                   ' "set /path_to_lhapdf/bin/lhapdf-config" from the MadGraph5_aMC@NLO python shell')
                content += 'LHAPDFPATH=\n' 
                content += 'PDFCODE=0\n'
        else:
            content += 'LHAPDFPATH=\n' 
            content += 'PDFCODE=0\n'

        content += 'ICKKW=%s\n' % self.banner.get_detail('run_card', 'ickkw')
        content += 'PTJCUT=%s\n' % self.banner.get_detail('run_card', 'ptj')
        # add the pythia8/hwpp path(s)
        if self.options['pythia8_path']:
            content+='PY8PATH=%s\n' % self.options['pythia8_path']
        if self.options['hwpp_path']:
            content+='HWPPPATH=%s\n' % self.options['hwpp_path']
        if self.options['thepeg_path']:
            content+='THEPEGPATH=%s\n' % self.options['thepeg_path']
        if self.options['hepmc_path']:
            content+='HEPMCPATH=%s\n' % self.options['hepmc_path']
        
        output = open(pjoin(self.me_dir, 'MCatNLO', 'banner.dat'), 'w')
        output.write(content)
        output.close()
        return shower


    def run_reweight(self, only):
        """runs the reweight_xsec_events eecutables on each sub-event file generated
        to compute on the fly scale and/or PDF uncertainities"""
        logger.info('   Doing reweight')

        nev_unw = pjoin(self.me_dir, 'SubProcesses', 'nevents_unweighted')
        # if only doing reweight, copy back the nevents_unweighted file
        if only:
            if os.path.exists(nev_unw + '.orig'):
                files.cp(nev_unw + '.orig', nev_unw)
            else:
                raise aMCatNLOError('Cannot find event file information')

        #read the nevents_unweighted file to get the list of event files
        file = open(nev_unw)
        lines = file.read().split('\n')
        file.close()
        # make copy of the original nevent_unweighted file
        files.cp(nev_unw, nev_unw + '.orig')
        # loop over lines (all but the last one whith is empty) and check that the
        #  number of events is not 0
        evt_files = [line.split()[0] for line in lines[:-1] if line.split()[1] != '0']
        #prepare the job_dict
        job_dict = {}
        exe = 'reweight_xsec_events.local'
        for i, evt_file in enumerate(evt_files):
            path, evt = os.path.split(evt_file)
            files.ln(pjoin(self.me_dir, 'SubProcesses', exe), \
                     pjoin(self.me_dir, 'SubProcesses', path))
            job_dict[path] = [exe]

        self.run_all(job_dict, [[evt, '1']], 'Running reweight')

        #check that the new event files are complete
        for evt_file in evt_files:
            last_line = subprocess.Popen(['tail',  '-n1', '%s.rwgt' % \
                    pjoin(self.me_dir, 'SubProcesses', evt_file)], \
                    stdout = subprocess.PIPE).stdout.read().strip()
            if last_line != "</LesHouchesEvents>":
                raise aMCatNLOError('An error occurred during reweight. Check the' + \
                        '\'reweight_xsec_events.output\' files inside the ' + \
                        '\'SubProcesses/P*/G*/ directories for details')

        #update file name in nevents_unweighted
        newfile = open(nev_unw, 'w')
        for line in lines:
            if line:
                newfile.write(line.replace(line.split()[0], line.split()[0] + '.rwgt') + '\n')
        newfile.close()

        return self.pdf_scale_from_reweighting(evt_files)

    def pdf_scale_from_reweighting(self, evt_files):
        """This function takes the files with the scale and pdf values
        written by the reweight_xsec_events.f code
        (P*/G*/pdf_scale_dependence.dat) and computes the overall
        scale and PDF uncertainty (the latter is computed using the
        Hessian method (if lhaid<90000) or Gaussian (if lhaid>90000))
        and returns it in percents.  The expected format of the file
        is: n_scales xsec_scale_central xsec_scale1 ...  n_pdf
        xsec_pdf0 xsec_pdf1 ...."""
        scale_pdf_info={}
        scales=[]
        pdfs=[]
        numofpdf = 0
        numofscales = 0
        for evt_file in evt_files:
            path, evt=os.path.split(evt_file)
            data_file=open(pjoin(self.me_dir, 'SubProcesses', path, 'scale_pdf_dependence.dat')).read()
            lines = data_file.replace("D", "E").split("\n")
            if not numofscales:
                numofscales = int(lines[0])
            if not numofpdf:
                numofpdf = int(lines[2])
            scales_this = [float(val) for val in lines[1].split()]
            pdfs_this = [float(val) for val in lines[3].split()]

            if numofscales != len(scales_this) or numofpdf !=len(pdfs_this):
                # the +1 takes the 0th (central) set into account
                logger.info(data_file)
                logger.info((' Expected # of scales: %d\n'+
                             ' Found # of scales: %d\n'+
                             ' Expected # of pdfs: %d\n'+
                             ' Found # of pdfs: %d\n') %
                        (numofscales, len(scales_this), numofpdf, len(pdfs_this)))
                raise aMCatNLOError('inconsistent scale_pdf_dependence.dat')
            if not scales:
                scales = [0.] * numofscales
            if not pdfs:
                pdfs = [0.] * numofpdf

            scales = [a + b for a, b in zip(scales, scales_this)]
            pdfs = [a + b for a, b in zip(pdfs, pdfs_this)]

        # get the central value
        if numofscales>0 and numofpdf==0:
            cntrl_val=scales[0]
        elif numofpdf>0 and numofscales==0:
            cntrl_val=pdfs[0]
        elif numofpdf>0 and numofscales>0:
            if abs(1-scales[0]/pdfs[0])>0.0001:
                raise aMCatNLOError('Central values for scale and PDF variation not identical')
            else:
                cntrl_val=scales[0]

        # get the scale uncertainty in percent
        scale_upp=0.0
        scale_low=0.0
        if numofscales>0:
            if cntrl_val != 0.0:
                scale_pdf_info['scale_upp'] = (max(scales)/cntrl_val-1)*100
                scale_pdf_info['scale_low'] = (1-min(scales)/cntrl_val)*100
            else:
                scale_pdf_info['scale_upp'] = 0.0
                scale_pdf_info['scale_low'] = 0.0


        # get the pdf uncertainty in percent (according to the Hessian method)
        lhaid=int(self.run_card['lhaid'])
        pdf_upp=0.0
        pdf_low=0.0
        if lhaid <= 90000:
            # use Hessian method (CTEQ & MSTW)
            if numofpdf>1:
                for i in range(int(numofpdf/2)):
                    pdf_upp=pdf_upp+math.pow(max(0.0,pdfs[2*i+1]-cntrl_val,pdfs[2*i+2]-cntrl_val),2)
                    pdf_low=pdf_low+math.pow(max(0.0,cntrl_val-pdfs[2*i+1],cntrl_val-pdfs[2*i+2]),2)
                if cntrl_val != 0.0:
                    scale_pdf_info['pdf_upp'] = math.sqrt(pdf_upp)/cntrl_val*100
                    scale_pdf_info['pdf_low'] = math.sqrt(pdf_low)/cntrl_val*100
                else:
                    scale_pdf_info['pdf_upp'] = 0.0
                    scale_pdf_info['pdf_low'] = 0.0

        else:
            # use Gaussian method (NNPDF)
            pdf_stdev=0.0
            for i in range(int(numofpdf-1)):
                pdf_stdev = pdf_stdev + pow(pdfs[i+1] - cntrl_val,2)
            pdf_stdev = math.sqrt(pdf_stdev/int(numofpdf-2))
            if cntrl_val != 0.0:
                scale_pdf_info['pdf_upp'] = pdf_stdev/cntrl_val*100
            else:
                scale_pdf_info['pdf_upp'] = 0.0
            scale_pdf_info['pdf_low'] = scale_pdf_info['pdf_upp']
        return scale_pdf_info


    def wait_for_complete(self, run_type):
        """this function waits for jobs on cluster to complete their run."""

        starttime = time.time()
        #logger.info('     Waiting for submitted jobs to complete')
        update_status = lambda i, r, f: self.update_status((i, r, f, run_type), 
                      starttime=starttime, level='parton', update_results=True)
        try:
            self.cluster.wait(self.me_dir, update_status)
        except:
            self.cluster.remove()
            raise

    def run_all(self, job_dict, arg_list, run_type='monitor', split_jobs = False):
        """runs the jobs in job_dict (organized as folder: [job_list]), with arguments args"""
        njob_split = 0
        self.ijob = 0

        #  this is to keep track, if splitting evt generation, of the various 
        # folders/args in order to resubmit the jobs if some of them fail
        self.split_folders = {}

        if run_type != 'shower':
            self.njobs = sum(len(jobs) for jobs in job_dict.values()) * len(arg_list)
            for args in arg_list:
                for Pdir, jobs in job_dict.items():
                    for job in jobs:
                        if not split_jobs:
                            self.run_exe(job, args, run_type, cwd=pjoin(self.me_dir, 'SubProcesses', Pdir) )
                        else:
                            for n in self.find_jobs_to_split(Pdir, job, args[1]):
                                self.run_exe(job, args + [n], run_type, cwd=pjoin(self.me_dir, 'SubProcesses', Pdir) )
                                njob_split += 1
                        # print some statistics if running serially
            if self.cluster_mode == 2:
                time.sleep(1) # security to allow all jobs to be launched
            if njob_split > 0:
                self.njobs = njob_split
        else:
            self.njobs = len(arg_list)
            for args in arg_list:
                [(cwd, exe)] = job_dict.items()
                self.run_exe(exe, args, run_type, cwd)
        
        self.wait_for_complete(run_type)



    def check_event_files(self):
        """check the integrity of the event files after splitting, and resubmit 
        those which are not nicely terminated"""
        to_resubmit = []
        for dir in self.split_folders.keys():
            last_line = ''
            try:
                last_line = subprocess.Popen(
                        ['tail', '-n1', pjoin(dir, 'events.lhe')], \
                    stdout = subprocess.PIPE).stdout.read().strip()
            except IOError:
                pass

            if last_line != "</LesHouchesEvents>":
                to_resubmit.append(dir)

        self.njobs = 0
        if to_resubmit:
            run_type = 'Resubmitting broken jobs'
            logger.info('Some event files are broken, corresponding jobs will be resubmitted.')
            logger.debug('Resubmitting\n' + '\n'.join(to_resubmit) + '\n')
            for dir in to_resubmit:
                files.rm([dir])
                job = self.split_folders[dir][0]
                args = self.split_folders[dir][1:]
                run_type = 'monitor'
                cwd = os.path.split(dir)[0]
                self.run_exe(job, args, run_type, cwd=cwd )
                self.njobs +=1

            self.wait_for_complete(run_type)


    def find_jobs_to_split(self, pdir, job, arg):
        """looks into the nevents_unweighed_splitted file to check how many
        split jobs are needed for this (pdir, job). arg is F, B or V"""
        # find the number of the integration channel
        splittings = []
        ajob = open(pjoin(self.me_dir, 'SubProcesses', pdir, job)).read()
        pattern = re.compile('for i in (\d+) ; do')
        match = re.search(pattern, ajob)
        channel = match.groups()[0]
        # then open the nevents_unweighted_splitted file and look for the 
        # number of splittings to be done
        nevents_file = open(pjoin(self.me_dir, 'SubProcesses', 'nevents_unweighted_splitted')).read()
        # This skips the channels with zero events, because they are
        # not of the form GFXX_YY, but simply GFXX
        pattern = re.compile(r"%s_(\d+)/events.lhe" % \
                          pjoin(pdir, 'G%s%s' % (arg,channel)))
        matches = re.findall(pattern, nevents_file)
        for m in matches:
            splittings.append(m)
        return splittings


    def run_exe(self, exe, args, run_type, cwd=None):
        """this basic function launch locally/on cluster exe with args as argument.
        """
        
        # first test that exe exists:
        execpath = None
        if cwd and os.path.exists(pjoin(cwd, exe)):
            execpath = pjoin(cwd, exe)
        elif not cwd and os.path.exists(exe):
            execpath = exe
        else:
            raise aMCatNLOError('Cannot find executable %s in %s' \
                % (exe, os.getcwd()))
        # check that the executable has exec permissions
        if self.cluster_mode == 1 and not os.access(execpath, os.X_OK):
            subprocess.call(['chmod', '+x', exe], cwd=cwd)
        # finally run it
        if self.cluster_mode == 0:
            #this is for the serial run
            misc.call(['./'+exe] + args, cwd=cwd)
            self.ijob += 1
            self.update_status((max([self.njobs - self.ijob - 1, 0]), 
                                min([1, self.njobs - self.ijob]),
                                self.ijob, run_type), level='parton')

        #this is for the cluster/multicore run
        elif 'reweight' in exe:
            # a reweight run
            # Find the correct PDF input file
            input_files, output_files = [], []
            pdfinput = self.get_pdf_input_filename()
            if os.path.exists(pdfinput):
                input_files.append(pdfinput)
            input_files.append(pjoin(os.path.dirname(exe), os.path.pardir, 'reweight_xsec_events'))
            input_files.append(pjoin(cwd, os.path.pardir, 'leshouche_info.dat'))
            input_files.append(args[0])
            output_files.append('%s.rwgt' % os.path.basename(args[0]))
            output_files.append('reweight_xsec_events.output')
            output_files.append('scale_pdf_dependence.dat')

            return self.cluster.submit2(exe, args, cwd=cwd, 
                             input_files=input_files, output_files=output_files,
                             required_output=output_files) 

        elif 'ajob' in exe:
            # the 'standard' amcatnlo job
            # check if args is a list of string 
            if type(args[0]) == str:
                input_files, output_files, required_output, args = self.getIO_ajob(exe,cwd, args)
                #submitting
                self.cluster.submit2(exe, args, cwd=cwd, 
                             input_files=input_files, output_files=output_files,
                             required_output=required_output)

                # keep track of folders and arguments for splitted evt gen
                subfolder=output_files[-1].split('/')[0]
                if len(args) == 4 and '_' in subfolder:
                    self.split_folders[pjoin(cwd,subfolder)] = [exe] + args

        elif 'shower' in exe:
            # a shower job
            # args are [shower, output(HEP or TOP), run_name]
            # cwd is the shower rundir, where the executable are found
            input_files, output_files = [], []
            shower = args[0]
            # the input files
            if shower == 'PYTHIA8':
                input_files.append(pjoin(cwd, 'Pythia8.exe'))
                input_files.append(pjoin(cwd, 'Pythia8.cmd'))
                if os.path.exists(pjoin(self.options['pythia8_path'], 'xmldoc')):
                    input_files.append(pjoin(cwd, 'config.sh'))
                    input_files.append(pjoin(self.options['pythia8_path'], 'xmldoc'))
                else:
                    input_files.append(pjoin(self.options['pythia8_path'], 'share/Pythia8/xmldoc'))
            else:
                input_files.append(pjoin(cwd, 'MCATNLO_%s_EXE' % shower))
                input_files.append(pjoin(cwd, 'MCATNLO_%s_input' % shower))
            if shower == 'HERWIGPP':
                input_files.append(pjoin(cwd, 'Herwig++'))
                input_files.append(pjoin(cwd, 'HepMCFortran.so'))
            if len(args) == 3:
                if os.path.exists(pjoin(self.me_dir, 'Events', self.run_name, 'events.lhe.gz')):
                    input_files.append(pjoin(self.me_dir, 'Events', self.run_name, 'events.lhe.gz'))
                elif os.path.exists(pjoin(self.me_dir, 'Events', self.run_name, 'events.lhe')):
                    input_files.append(pjoin(self.me_dir, 'Events', self.run_name, 'events.lhe'))
                else:
                    raise aMCatNLOError, 'Event file not present in %s' % \
                            pjoin(self.me_dir, 'Events', self.run_name)
            else: 
                input_files.append(pjoin(cwd, 'events_%s.lhe' % args[3]))
            # the output files
            if len(args) == 3:
                output_files.append('mcatnlo_run.log')
            else:
                output_files.append('mcatnlo_run_%s.log' % args[3]) 
            if args[1] == 'HEP':
                if len(args) == 3:
                    fname = 'events'
                else:
                    fname = 'events_%s' % args[3]
                if shower in ['PYTHIA8', 'HERWIGPP']:
                    output_files.append(fname + '.hepmc.gz')
                else:
                    output_files.append(fname + '.hep.gz')
            elif args[1] == 'TOP':
                if len(args) == 3:
                    fname = 'topfile'
                else:
                    fname = 'topfile_%s' % args[3]
                output_files.append(fname + '.tar')
            else:
                raise aMCatNLOError, 'Not a valid output argument for shower job :  %d' % args[1]
            #submitting
            self.cluster.submit2(exe, args, cwd=cwd, 
                    input_files=input_files, output_files=output_files)

        else:
            return self.cluster.submit(exe, args, cwd=cwd)

    def getIO_ajob(self,exe,cwd, args):
        # use local disk if possible => need to stands what are the 
        # input/output files
        
        keep_fourth_arg = False
        output_files = []
        required_output = []
        input_files = [pjoin(self.me_dir, 'MGMEVersion.txt'),
                     pjoin(self.me_dir, 'SubProcesses', 'randinit'),
                     pjoin(cwd, 'symfact.dat'),
                     pjoin(cwd, 'iproc.dat'),
                     pjoin(cwd, 'initial_states_map.dat'),
                     pjoin(cwd, 'configs_and_props_info.dat'),
                     pjoin(cwd, 'leshouche_info.dat'),
                     pjoin(cwd, 'param_card.dat'),
                     pjoin(cwd, 'FKS_params.dat')]

        if os.path.exists(pjoin(cwd,'nevents.tar')):
            input_files.append(pjoin(cwd,'nevents.tar'))
        
        if os.path.exists(pjoin(self.me_dir,'SubProcesses','OLE_order.olc')):
            input_files.append(pjoin(cwd, 'OLE_order.olc'))

        # File for the loop (might not be present if MadLoop is not used)
        if os.path.exists(pjoin(cwd,'MadLoop5_resources')):
            input_files.append(pjoin(cwd, 'MadLoop5_resources.tar.gz'))
            if not os.path.exists(pjoin(cwd,'MadLoop5_resources.tar.gz')):
                tf=tarfile.open(pjoin(cwd,'MadLoop5_resources.tar.gz'),'w:gz',
                                                                 dereference=True)
                tf.add(pjoin(cwd,'MadLoop5_resources'),arcname='MadLoop5_resources')
                tf.close()

        Ire = re.compile("for i in ([\d\s]*) ; do")
        try : 
            fsock = open(exe)
        except IOError:
            fsock = open(pjoin(cwd,exe))
        text = fsock.read()
        data = Ire.findall(text)
        subdir = ' '.join(data).split()
               
        if args[0] == '0':
            # MADEVENT MINT FO MODE
            input_files.append(pjoin(cwd, 'madevent_mintFO'))
            input_files.append(pjoin(self.me_dir, 'SubProcesses','madin.%s' % args[1]))
            #j=$2\_G$i
            for i in subdir:
                current = '%s_G%s' % (args[1],i)
                if os.path.exists(pjoin(cwd,current)):
                    input_files.append(pjoin(cwd, current))
                output_files.append(current)

                required_output.append('%s/results.dat' % current)
                required_output.append('%s/log.txt' % current)
                required_output.append('%s/mint_grids' % current)
                required_output.append('%s/grid.MC_integer' % current)
                if len(args) == 4:
                    required_output.append('%s/scale_pdf_dependence.dat' % current)
                    args[2] = '-1'
                    # use a grid train on another part
                    base = '%s_G%s' % (args[3],i)
                    if args[0] == '0':
                        to_move = ['grid.MC_integer','mint_grids']
                    elif args[0] == '1':
                        to_move = ['mint_grids', 'grid.MC_integer']
                    else: 
                        to_move  = []
                    if self.run_card['iappl'] =='2':
                        for grid in glob.glob(pjoin(cwd,base,'grid_obs_*_in.root')):
                            to_move.append(grid)
                    if not os.path.exists(pjoin(cwd,current)):
                        os.mkdir(pjoin(cwd,current))
                        input_files.append(pjoin(cwd, current))
                    for name in to_move:
                        files.cp(pjoin(cwd,base, name), 
                                        pjoin(cwd,current))
                    files.cp(pjoin(cwd,base, 'grid.MC_integer'), 
                                        pjoin(cwd,current))
                            
        elif args[0] == '2':
            # MINTMC MODE
            input_files.append(pjoin(cwd, 'madevent_mintMC'))
            if args[2] in ['0','2']:
                input_files.append(pjoin(self.me_dir, 'SubProcesses','madinMMC_%s.2' % args[1]))

            for i in subdir:
                current = 'G%s%s' % (args[1], i)
                if os.path.exists(pjoin(cwd,current)):
                    input_files.append(pjoin(cwd, current))
                output_files.append(current)
                if len(args) == 4 and args[3] in ['H','S','V','B','F']:
                    # use a grid train on another part
                    base = '%s_%s' % (args[3],i)
                    files.ln(pjoin(cwd,base,'mint_grids'), name = 'preset_mint_grids', 
                                            starting_dir=pjoin(cwd,current))
                    files.ln(pjoin(cwd,base,'grid.MC_integer'), 
                                          starting_dir=pjoin(cwd,current))
                elif len(args) ==4:
                    keep_fourth_arg = True
                    # this is for the split event generation
                    output_files.append('G%s%s_%s' % (args[1], i, args[3]))
                    required_output.append('G%s%s_%s/log_MINT%s.txt' % (args[1], i, args[3],args[2]))

                else:
                    required_output.append('%s/log_MINT%s.txt' % (current,args[2]))
                if args[2] in ['0','1']:
                    required_output.append('%s/results.dat' % current)
                if args[2] == '1':
                    output_files.append('%s/results.dat' % current)

        else:
            raise aMCatNLOError, 'not valid arguments: %s' %(', '.join(args))

        #Find the correct PDF input file
        pdfinput = self.get_pdf_input_filename()
        if os.path.exists(pdfinput):
            input_files.append(pdfinput)

        if len(args) == 4 and not keep_fourth_arg:
            args = args[:3]
            
        return input_files, output_files, required_output,  args
            
    def write_madinMMC_file(self, path, run_mode, mint_mode):
        """writes the madinMMC_?.2 file"""
        #check the validity of the arguments
        run_modes = ['born', 'virt', 'novi', 'all', 'viSB', 'novB']
        if run_mode not in run_modes:
            raise aMCatNLOError('%s is not a valid mode for run. Please use one of the following: %s' \
                    % (run_mode, ', '.join(run_modes)))
        mint_modes = [0, 1, 2]
        if mint_mode not in mint_modes:
            raise aMCatNLOError('%s is not a valid mode for mintMC. Please use one of the following: %s' \
                    % (mint_mode, ', '.join(mint_modes)))
        if run_mode in ['born']:
            name_suffix = 'B'
        elif run_mode in ['virt', 'viSB']:
            name_suffix = 'V'
        else:
            name_suffix = 'F'

        content = \
"""-1 12      ! points, iterations
0.03       ! desired fractional accuracy
1 -0.1     ! alpha, beta for Gsoft
-1 -0.1    ! alpha, beta for Gazi
1          ! Suppress amplitude (0 no, 1 yes)?
1          ! Exact helicity sum (0 yes, n = number/event)?
1          ! Enter Configuration Number:
%1d          ! MINT imode: 0 to set-up grids, 1 to perform integral, 2 generate events
1 1 1      ! if imode is 1: Folding parameters for xi_i, phi_i and y_ij
%s        ! all, born, real, virt
""" \
                    % (mint_mode, run_mode)
        file = open(pjoin(path, 'madinMMC_%s.2' % name_suffix), 'w')
        file.write(content)
        file.close()

    def write_madin_file(self, path, run_mode, vegas_mode, npoints, niters, accuracy='0'):
        """writes the madin.run_mode file"""
        #check the validity of the arguments
        run_modes = ['born', 'virt', 'novi', 'all', 'viSB', 'novB', 'grid']
        if run_mode not in run_modes:
            raise aMCatNLOError('%s is not a valid mode for run. Please use one of the following: %s' \
                    % (run_mode, ', '.join(run_modes)))
        name_suffix = run_mode

        content = \
"""%s %s  ! points, iterations
%s ! accuracy
2 ! 0 fixed grid 2 adjust
1 ! 1 suppress amp, 0 doesnt
1 ! 0 for exact hel sum
1 ! hel configuration numb
'test'
1 ! 1 to save grids
%s ! 0 to exclude, 1 for new run, 2 to restart, 3 to reset w/ keeping grid
%s        ! all, born, real, virt
""" \
                    % (npoints,niters,accuracy,vegas_mode,run_mode)
        file = open(pjoin(path, 'madin.%s' % name_suffix), 'w')
        file.write(content)
        file.close()

    def compile(self, mode, options):
        """compiles aMC@NLO to compute either NLO or NLO matched to shower, as
        specified in mode"""

        os.mkdir(pjoin(self.me_dir, 'Events', self.run_name))

        self.banner.write(pjoin(self.me_dir, 'Events', self.run_name, 
                          '%s_%s_banner.txt' % (self.run_name, self.run_tag)))

        self.get_characteristics(pjoin(self.me_dir, 
                                        'SubProcesses', 'proc_characteristics'))

        #define a bunch of log files
        amcatnlo_log = pjoin(self.me_dir, 'compile_amcatnlo.log')
        madloop_log = pjoin(self.me_dir, 'compile_madloop.log')
        reweight_log = pjoin(self.me_dir, 'compile_reweight.log')
        test_log = pjoin(self.me_dir, 'test.log')

        self.update_status('Compiling the code', level=None, update_results=True)


        libdir = pjoin(self.me_dir, 'lib')
        sourcedir = pjoin(self.me_dir, 'Source')

        #clean files
        files.rm([amcatnlo_log, madloop_log, reweight_log, test_log])
        #define which executable/tests to compile
        if '+' in mode:
            mode = mode.split('+')[0]
        if mode in ['NLO', 'LO']:
            exe = 'madevent_mintFO'
            tests = ['test_ME']
            self.analyse_card.write_card(pjoin(self.me_dir, 'SubProcesses', 'analyse_opts'))
        elif mode in ['aMC@NLO', 'aMC@LO','noshower','noshowerLO']:
            exe = 'madevent_mintMC'
            tests = ['test_ME', 'test_MC']
            # write an analyse_opts with a dummy analysis so that compilation goes through
            open(pjoin(self.me_dir, 'SubProcesses', 'analyse_opts'),'w').write('FO_ANALYSE=analysis_dummy.o dbook.o open_output_files_dummy.o\n')

        #directory where to compile exe
        p_dirs = [d for d in \
                open(pjoin(self.me_dir, 'SubProcesses', 'subproc.mg')).read().split('\n') if d]
        # create param_card.inc and run_card.inc
        self.do_treatcards('', amcatnlo=True)
        # if --nocompile option is specified, check here that all exes exists. 
        # If they exists, return
        if all([os.path.exists(pjoin(self.me_dir, 'SubProcesses', p_dir, exe)) \
                for p_dir in p_dirs]) and options['nocompile']:
            return

        # rm links to lhapdflib/ PDFsets if exist
        if os.path.exists(pjoin(libdir, 'PDFsets')):
            files.rm(pjoin(libdir, 'PDFsets'))

        # read the run_card to find if lhapdf is used or not
        if self.run_card['pdlabel'] == 'lhapdf' and \
                (self.banner.get_detail('run_card', 'lpp1') != '0' or \
                 self.banner.get_detail('run_card', 'lpp1') != '0'):

            self.link_lhapdf(libdir, [pjoin('SubProcesses', p) for p in p_dirs])
            pdfsetsdir = self.get_lhapdf_pdfsetsdir()
            lhaid_list = [int(self.run_card['lhaid'])]
            if self.run_card['reweight_PDF'].lower() == '.true.':
                lhaid_list.append(int(self.run_card['PDF_set_min']))
                lhaid_list.append(int(self.run_card['PDF_set_max']))
            self.copy_lhapdf_set(lhaid_list, pdfsetsdir)

        else:
            if self.run_card['lpp1'] == '1' == self.run_card['lpp2']:
                logger.info('Using built-in libraries for PDFs')
            if self.run_card['lpp1'] == '0' == self.run_card['lpp2']:
                logger.info('Lepton-Lepton collision: Ignoring \'pdlabel\' and \'lhaid\' in the run_card.')
            try:
                del os.environ['lhapdf']
            except KeyError:
                pass

        # read the run_card to find if applgrid is used or not
        if self.run_card['iappl'] != '0':
            os.environ['applgrid'] = 'True'
            # check versions of applgrid and amcfast
            for code in ['applgrid','amcfast']:
                try:
                    p = subprocess.Popen([self.options[code], '--version'], \
                                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                except OSError:
                    raise aMCatNLOError(('No valid %s installation found. \n' + \
                       'Please set the path to %s-config by using \n' + \
                       'MG5_aMC> set <absolute-path-to-%s>/bin/%s-config \n') % (code,code,code,code))
                else:
                    output, _ = p.communicate()
                    if code is 'applgrid' and output < '1.4.63':
                        raise aMCatNLOError('Version of APPLgrid is too old. Use 1.4.69 or later.'\
                                             +' You are using %s',output)
                    if code is 'amcfast' and output < '1.1.1':
                        raise aMCatNLOError('Version of aMCfast is too old. Use 1.1.1 or later.'\
                                             +' You are using %s',output)
                
            # set-up the Source/make_opts with the correct applgrid-config file
            appllibs="  APPLLIBS=$(shell %s --ldflags) $(shell %s --ldcflags) \n" \
                             % (self.options['amcfast'],self.options['applgrid'])
            text=open(pjoin(self.me_dir,'Source','make_opts'),'r').readlines()
            text_out=[]
            for line in text:
                if line.strip().startswith('APPLLIBS=$'):
                    line=appllibs
                text_out.append(line)
            open(pjoin(self.me_dir,'Source','make_opts'),'w').writelines(text_out)
        else:
            try:
                del os.environ['applgrid']
            except KeyError:
                pass

        try: 
            os.environ['fastjet_config'] = self.options['fastjet']
        except (TypeError, KeyError):
            if 'fastjet_config' in os.environ:
                del os.environ['fastjet_config']
            os.unsetenv('fastjet_config')
        
        # make Source
        self.update_status('Compiling source...', level=None)
        misc.compile(['clean4pdf'], cwd = sourcedir)
        misc.compile(cwd = sourcedir)
        if os.path.exists(pjoin(libdir, 'libdhelas.a')) \
          and os.path.exists(pjoin(libdir, 'libgeneric.a')) \
          and os.path.exists(pjoin(libdir, 'libmodel.a')) \
          and os.path.exists(pjoin(libdir, 'libpdf.a')):
            logger.info('          ...done, continuing with P* directories')
        else:
            raise aMCatNLOError('Compilation failed')
        
        # make StdHep (only necessary with MG option output_dependencies='internal')
        MCatNLO_libdir = pjoin(self.me_dir, 'MCatNLO', 'lib')
        if not os.path.exists(os.path.realpath(pjoin(MCatNLO_libdir, 'libstdhep.a'))) or \
            not os.path.exists(os.path.realpath(pjoin(MCatNLO_libdir, 'libFmcfio.a'))):  
            if  os.path.exists(pjoin(sourcedir,'StdHEP')):
                logger.info('Compiling StdHEP (can take a couple of minutes) ...')
                misc.compile(['StdHEP'], cwd = sourcedir)
                logger.info('          ...done.')      
            else:
                raise aMCatNLOError('Could not compile StdHEP because its'+\
                   ' source directory could not be found in the SOURCE folder.\n'+\
                             " Check the MG5_aMC option 'output_dependencies.'")

        # make CutTools (only necessary with MG option output_dependencies='internal')
        if not os.path.exists(os.path.realpath(pjoin(libdir, 'libcts.a'))) or \
            not os.path.exists(os.path.realpath(pjoin(libdir, 'mpmodule.mod'))):
            if  os.path.exists(pjoin(sourcedir,'CutTools')):
                logger.info('Compiling CutTools (can take a couple of minutes) ...')
                misc.compile(['CutTools'], cwd = sourcedir)
                logger.info('          ...done.')
            else:
                raise aMCatNLOError('Could not compile CutTools because its'+\
                   ' source directory could not be found in the SOURCE folder.\n'+\
                             " Check the MG5_aMC option 'output_dependencies.'")
        if not os.path.exists(os.path.realpath(pjoin(libdir, 'libcts.a'))) or \
            not os.path.exists(os.path.realpath(pjoin(libdir, 'mpmodule.mod'))):
            raise aMCatNLOError('CutTools compilation failed.')            

        # Verify compatibility between current compiler and the one which was
        # used when last compiling CutTools (if specified).
        compiler_log_path = pjoin(os.path.dirname((os.path.realpath(pjoin(
                                  libdir, 'libcts.a')))),'compiler_version.log')
        if os.path.exists(compiler_log_path):
            compiler_version_used = open(compiler_log_path,'r').read()
            if not str(misc.get_gfortran_version(misc.detect_current_compiler(\
                       pjoin(sourcedir,'make_opts')))) in compiler_version_used:
                if os.path.exists(pjoin(sourcedir,'CutTools')):
                    logger.info('CutTools was compiled with a different fortran'+\
                                            ' compiler. Re-compiling it now...')
                    misc.compile(['cleanCT'], cwd = sourcedir)
                    misc.compile(['CutTools'], cwd = sourcedir)
                    logger.info('          ...done.')
                else:
                    raise aMCatNLOError("CutTools installation in %s"\
                                 %os.path.realpath(pjoin(libdir, 'libcts.a'))+\
                 " seems to have been compiled with a different compiler than"+\
                    " the one specified in MG5_aMC. Please recompile CutTools.")

        # make IREGI (only necessary with MG option output_dependencies='internal')
        if not os.path.exists(os.path.realpath(pjoin(libdir, 'libiregi.a'))) \
           and os.path.exists(pjoin(sourcedir,'IREGI')):
                logger.info('Compiling IREGI (can take a couple of minutes) ...')
                misc.compile(['IREGI'], cwd = sourcedir)
                logger.info('          ...done.')

        if os.path.exists(pjoin(libdir, 'libiregi.a')):
            # Verify compatibility between current compiler and the one which was
            # used when last compiling IREGI (if specified).
            compiler_log_path = pjoin(os.path.dirname((os.path.realpath(pjoin(
                                libdir, 'libiregi.a')))),'compiler_version.log')
            if os.path.exists(compiler_log_path):
                compiler_version_used = open(compiler_log_path,'r').read()
                if not str(misc.get_gfortran_version(misc.detect_current_compiler(\
                       pjoin(sourcedir,'make_opts')))) in compiler_version_used:
                    if os.path.exists(pjoin(sourcedir,'IREGI')):
                        logger.info('IREGI was compiled with a different fortran'+\
                                            ' compiler. Re-compiling it now...')
                        misc.compile(['cleanIR'], cwd = sourcedir)
                        misc.compile(['IREGI'], cwd = sourcedir)
                        logger.info('          ...done.')
                    else:
                        raise aMCatNLOError("IREGI installation in %s"\
                                %os.path.realpath(pjoin(libdir, 'libiregi.a'))+\
                 " seems to have been compiled with a different compiler than"+\
                    " the one specified in MG5_aMC. Please recompile IREGI.")

        # check if MadLoop virtuals have been generated
        if self.proc_characteristics['has_loops'].lower() == 'true' and \
                          not os.path.exists(pjoin(self.me_dir,'OLP_virtuals')):
            os.environ['madloop'] = 'true'
            if mode in ['NLO', 'aMC@NLO', 'noshower']:
                tests.append('check_poles')
        else:
            os.unsetenv('madloop')

        # make and run tests (if asked for), gensym and make madevent in each dir
        self.update_status('Compiling directories...', level=None)

        for test in tests:
            self.write_test_input(test)

        try:
            import multiprocessing
            if not self.nb_core:
                try:
                    self.nb_core = int(self.options['nb_core'])
                except TypeError:
                    self.nb_core = multiprocessing.cpu_count()
        except ImportError: 
            self.nb_core = 1

        compile_options = copy.copy(self.options)
        compile_options['nb_core'] = self.nb_core
        compile_cluster = cluster.MultiCore(**compile_options)
        logger.info('Compiling on %d cores' % self.nb_core)

        update_status = lambda i, r, f: self.donothing(i,r,f)
        for p_dir in p_dirs:
            compile_cluster.submit(prog = compile_dir, 
                               argument = [self.me_dir, p_dir, mode, options, 
                    tests, exe, self.options['run_mode']])
        try:
            compile_cluster.wait(self.me_dir, update_status)

        except:
            compile_cluster.remove()
            self.quit()

        logger.info('Checking test output:')
        for p_dir in p_dirs:
            logger.info(p_dir)
            for test in tests:
                logger.info(' Result for %s:' % test)

                this_dir = pjoin(self.me_dir, 'SubProcesses', p_dir) 
                #check that none of the tests failed
                self.check_tests(test, this_dir)


    def donothing(*args):
        pass


    def check_tests(self, test, dir):
        """just call the correct parser for the test log"""
        if test in ['test_ME', 'test_MC']:
            return self.parse_test_mx_log(pjoin(dir, '%s.log' % test)) 
        elif test == 'check_poles':
            return self.parse_check_poles_log(pjoin(dir, '%s.log' % test)) 


    def parse_test_mx_log(self, log):
        """read and parse the test_ME/MC.log file"""
        content = open(log).read()
        if 'FAILED' in content:
            logger.info('Output of the failing test:\n'+content[:-1],'$MG:color:BLACK')
            raise aMCatNLOError('Some tests failed, run cannot continue.\n' + \
                'Please check that widths of final state particles (e.g. top) have been' + \
                ' set to 0 in the param_card.dat.')
        else:
            lines = [l for l in content.split('\n') if 'PASSED' in l]
            logger.info('   Passed.')
            logger.debug('\n'+'\n'.join(lines))


    def parse_check_poles_log(self, log):
        """reads and parse the check_poles.log file"""
        content = open(log).read()
        npass = 0
        nfail = 0
        for line in content.split('\n'):
            if 'PASSED' in line:
                npass +=1
                tolerance = float(line.split()[1])
            if 'FAILED' in line:
                nfail +=1
                tolerance = float(line.split()[1])

        if nfail + npass == 0:
            logger.warning('0 points have been tried')
            return

        if float(nfail)/float(nfail+npass) > 0.1:
            raise aMCatNLOError('Poles do not cancel, run cannot continue')
        else:
            logger.info('   Poles successfully cancel for %d points over %d (tolerance=%2.1e)' \
                    %(npass, nfail+npass, tolerance))


    def write_test_input(self, test):
        """write the input files to run test_ME/MC or check_poles"""
        if test in ['test_ME', 'test_MC']:
            content = "-2 -2\n" #generate randomly energy/angle
            content+= "100 100\n" #run 100 points for soft and collinear tests
            content+= "0\n" #sum over helicities
            content+= "0\n" #all FKS configs
            content+= '\n'.join(["-1"] * 50) #random diagram
        elif test == 'check_poles':
            content = '20 \n -1\n'
        
        file = open(pjoin(self.me_dir, '%s_input.txt' % test), 'w')
        if test == 'test_MC':
            shower = self.run_card['parton_shower']
            MC_header = "%s\n " % shower + \
                        "1 \n1 -0.1\n-1 -0.1\n"
            file.write(MC_header + content)
        else:
            file.write(content)
        file.close()



    ############################################################################
    def find_model_name(self):
        """ return the model name """
        if hasattr(self, 'model_name'):
            return self.model_name
        
        model = 'sm'
        proc = []
        for line in open(os.path.join(self.me_dir,'Cards','proc_card_mg5.dat')):
            line = line.split('#')[0]
            #line = line.split('=')[0]
            if line.startswith('import') and 'model' in line:
                model = line.split()[2]   
                proc = []
            elif line.startswith('generate'):
                proc.append(line.split(None,1)[1])
            elif line.startswith('add process'):
                proc.append(line.split(None,2)[2])
       
        self.model = model
        self.process = proc 
        return model



    ############################################################################
    def ask_run_configuration(self, mode, options, switch={}):
        """Ask the question when launching generate_events/multi_run"""
        
        if 'parton' not in options:
            options['parton'] = False
        if 'reweightonly' not in options:
            options['reweightonly'] = False
        
        
        void = 'NOT INSTALLED'
        switch_order = ['order', 'fixed_order', 'shower','madspin']
        switch_default = {'order': 'NLO', 'fixed_order': 'OFF', 'shower': void,
                  'madspin': void}
        if not switch:
            switch = switch_default
        else:
            switch.update(dict((k,value) for k,v in switch_default.items() if k not in switch))

        default_switch = ['ON', 'OFF']
        allowed_switch_value = {'order': ['LO', 'NLO'],
                                'fixed_order': default_switch,
                                'shower': default_switch,
                                'madspin': default_switch}
        
        description = {'order':  'Perturbative order of the calculation:',
                       'fixed_order': 'Fixed order (no event generation and no MC@[N]LO matching):',
                       'shower': 'Shower the generated events:',
                       'madspin': 'Decay particles with the MadSpin module:' }

        force_switch = {('shower', 'ON'): {'fixed_order': 'OFF'},
                       ('madspin', 'ON'): {'fixed_order':'OFF'},
                       ('fixed_order', 'ON'): {'shower': 'OFF', 'madspin': 'OFF'}
                       }
        special_values = ['LO', 'NLO', 'aMC@NLO', 'aMC@LO', 'noshower', 'noshowerLO']

        assign_switch = lambda key, value: switch.__setitem__(key, value if switch[key] != void else void )
        

        if mode == 'auto': 
            mode = None
        if not mode and (options['parton'] or options['reweightonly']):
            mode = 'noshower'         
        
        # Init the switch value according to the current status
        available_mode = ['0', '1', '2']
        available_mode.append('3')
        if os.path.exists(pjoin(self.me_dir, 'Cards', 'shower_card.dat')):
            switch['shower'] = 'ON'
        else:
            switch['shower'] = 'OFF'
                
        if not aMCatNLO or self.options['mg5_path']:
            available_mode.append('4')
            if os.path.exists(pjoin(self.me_dir,'Cards','madspin_card.dat')):
                switch['madspin'] = 'ON'
            else:
                switch['madspin'] = 'OFF'
            
        answers = list(available_mode) + ['auto', 'done']
        alias = {}
        for id, key in enumerate(switch_order):
            if switch[key] != void:
                answers += ['%s=%s' % (key, s) for s in allowed_switch_value[key]]
                #allow lower case for on/off
                alias.update(dict(('%s=%s' % (key, s.lower()), '%s=%s' % (key, s))
                                   for s in allowed_switch_value[key]))
        answers += special_values
        
        def create_question(switch):
            switch_format = " %i %-60s %12s=%s\n"
            question = "The following switches determine which operations are executed:\n"
            for id, key in enumerate(switch_order):
                question += switch_format % (id+1, description[key], key, switch[key])
            question += '  Either type the switch number (1 to %s) to change its default setting,\n' % (id+1)
            question += '  or set any switch explicitly (e.g. type \'order=LO\' at the prompt)\n'
            question += '  Type \'0\', \'auto\', \'done\' or just press enter when you are done.\n'
            return question


        def modify_switch(mode, answer, switch):
            if '=' in answer:
                key, status = answer.split('=')
                switch[key] = status
                if (key, status) in force_switch:
                    for key2, status2 in force_switch[(key, status)].items():
                        if switch[key2] not in  [status2, void]:
                            logger.info('For coherence \'%s\' is set to \'%s\''
                                        % (key2, status2), '$MG:color:BLACK')
                            switch[key2] = status2
            elif answer in ['0', 'auto', 'done']:
                return 
            elif answer in special_values:
                logger.info('Enter mode value: Go to the related mode', '$MG:color:BLACK')
                if answer == 'LO':
                    switch['order'] = 'LO'
                    switch['fixed_order'] = 'ON'
                    assign_switch('shower', 'OFF')
                    assign_switch('madspin', 'OFF')
                elif answer == 'NLO':
                    switch['order'] = 'NLO'
                    switch['fixed_order'] = 'ON'
                    assign_switch('shower', 'OFF')
                    assign_switch('madspin', 'OFF')
                elif answer == 'aMC@NLO':
                    switch['order'] = 'NLO'
                    switch['fixed_order'] = 'OFF'
                    assign_switch('shower', 'ON')
                    assign_switch('madspin', 'OFF')
                elif answer == 'aMC@LO':
                    switch['order'] = 'LO'
                    switch['fixed_order'] = 'OFF'
                    assign_switch('shower', 'ON')
                    assign_switch('madspin', 'OFF')
                elif answer == 'noshower':
                    switch['order'] = 'NLO'
                    switch['fixed_order'] = 'OFF'
                    assign_switch('shower', 'OFF')
                    assign_switch('madspin', 'OFF')                                                    
                elif answer == 'noshowerLO':
                    switch['order'] = 'LO'
                    switch['fixed_order'] = 'OFF'
                    assign_switch('shower', 'OFF')
                    assign_switch('madspin', 'OFF')
                if mode:
                    return
            return switch


        modify_switch(mode, self.last_mode, switch)
        if switch['madspin'] == 'OFF' and  os.path.exists(pjoin(self.me_dir,'Cards','madspin_card.dat')):
            assign_switch('madspin', 'ON')
        
        if not self.force:
            answer = ''
            while answer not in ['0', 'done', 'auto', 'onlyshower']:
                question = create_question(switch)
                if mode:
                    answer = mode
                else:
                    answer = self.ask(question, '0', answers, alias=alias)
                if answer.isdigit() and answer != '0':
                    key = switch_order[int(answer) - 1]
                    opt1 = allowed_switch_value[key][0]
                    opt2 = allowed_switch_value[key][1]
                    answer = '%s=%s' % (key, opt1 if switch[key] == opt2 else opt2)

                if not modify_switch(mode, answer, switch):
                    break

        #assign the mode depending of the switch
        if not mode or mode == 'auto':
            if switch['order'] == 'LO':
                if switch['shower'] == 'ON':
                    mode = 'aMC@LO'
                elif switch['fixed_order'] == 'ON':
                    mode = 'LO'
                else:
                    mode =  'noshowerLO'
            elif switch['order'] == 'NLO':
                if switch['shower'] == 'ON':
                    mode = 'aMC@NLO'
                elif switch['fixed_order'] == 'ON':
                    mode = 'NLO'
                else:
                    mode =  'noshower'  
        logger.info('will run in mode: %s' % mode)                

        if mode == 'noshower':
            logger.warning("""You have chosen not to run a parton shower. NLO events without showering are NOT physical.
Please, shower the Les Houches events before using them for physics analyses.""")            
            
        
        # specify the cards which are needed for this run.
        cards = ['param_card.dat', 'run_card.dat']
        ignore = []
        if mode in ['LO', 'NLO']:
            options['parton'] = True
            ignore = ['shower_card.dat', 'madspin_card.dat']
            cards.append('FO_analyse_card.dat')
        elif switch['madspin'] == 'ON':
            cards.append('madspin_card.dat')
        if 'aMC@' in mode:
            cards.append('shower_card.dat')
        if mode == 'onlyshower':
            cards = ['shower_card.dat']
        if options['reweightonly']:
            cards = ['run_card.dat']

        self.keep_cards(cards, ignore)
        
        if mode =='onlyshower':
            cards = ['shower_card.dat']
        
        if not options['force'] and not self.force:
            self.ask_edit_cards(cards, plot=False)

        self.banner = banner_mod.Banner()

        # store the cards in the banner
        for card in cards:
            self.banner.add(pjoin(self.me_dir, 'Cards', card))
        # and the run settings
        run_settings = '\n'.join(['%s = %s' % (k, v) for (k, v) in switch.items()])
        self.banner.add_text('run_settings', run_settings)

        if not mode =='onlyshower':
            self.run_card = self.banner.charge_card('run_card')
            self.run_tag = self.run_card['run_tag']
            #this is if the user did not provide a name for the current run
            if not hasattr(self, 'run_name') or not self.run_name:
                self.run_name = self.find_available_run_name(self.me_dir)
                #add a tag in the run_name for distinguish run_type
                if self.run_name.startswith('run_'):
                    if mode in ['LO','aMC@LO','noshowerLO']:
                        self.run_name += '_LO' 
            self.set_run_name(self.run_name, self.run_tag, 'parton')
            if int(self.run_card['ickkw']) == 3 and mode in ['LO', 'aMC@LO', 'noshowerLO']:
                logger.error("""FxFx merging (ickkw=3) not allowed at LO""")
                raise self.InvalidCmd(error)
            elif int(self.run_card['ickkw']) == 3 and mode in ['aMC@NLO', 'noshower']:
                logger.warning("""You are running with FxFx merging enabled.  To be able to merge
    samples of various multiplicities without double counting, you
    have to remove some events after showering 'by hand'.  Please
    read http://amcatnlo.cern.ch/FxFx_merging.htm for more details.""")
                if self.run_card['parton_shower'].upper() == 'PYTHIA6Q':
                    logger.error("""FxFx merging does not work with Q-squared ordered showers.""")
                    raise self.InvalidCmd(error)
                elif self.run_card['parton_shower'].upper() != 'HERWIG6' and self.run_card['parton_shower'].upper() != 'PYTHIA8':
                    question="FxFx merging not tested for %s shower. Do you want to continue?\n"  % self.run_card['parton_shower'] + \
                        "Type \'n\' to stop or \'y\' to continue"
                    answers = ['n','y']
                    answer = self.ask(question, 'n', answers, alias=alias)
                    if answer == 'n':
                        error = '''Stop opertation'''
                        self.ask_run_configuration(mode, options)
    #                    raise aMCatNLOError(error)
        if 'aMC@' in mode or mode == 'onlyshower':
            self.shower_card = self.banner.charge_card('shower_card')
            
        elif mode in ['LO', 'NLO']:
            analyse_card_path = pjoin(self.me_dir, 'Cards','FO_analyse_card.dat')
            self.analyse_card = self.banner.charge_card('FO_analyse_card')

        
        return mode


#===============================================================================
# aMCatNLOCmd
#===============================================================================
class aMCatNLOCmdShell(aMCatNLOCmd, cmd.CmdShell):
    """The command line processor of MadGraph"""  

_compile_usage = "compile [MODE] [options]\n" + \
                "-- compiles aMC@NLO \n" + \
                "   MODE can be either FO, for fixed-order computations, \n" + \
                "   or MC for matching with parton-shower monte-carlos. \n" + \
                "   (if omitted, it is set to MC)\n"
_compile_parser = misc.OptionParser(usage=_compile_usage)
_compile_parser.add_option("-f", "--force", default=False, action='store_true',
                                help="Use the card present in the directory for the launch, without editing them")

_launch_usage = "launch [MODE] [options]\n" + \
                "-- execute aMC@NLO \n" + \
                "   MODE can be either LO, NLO, aMC@NLO or aMC@LO (if omitted, it is asked in a separate question)\n" + \
                "     If mode is set to LO/NLO, no event generation will be performed, but only the \n" + \
                "     computation of the total cross-section and the filling of parton-level histograms \n" + \
                "     specified in the DIRPATH/SubProcesses/madfks_plot.f file.\n" + \
                "     If mode is set to aMC@LO/aMC@NLO, after the cross-section computation, a .lhe \n" + \
                "     event file is generated which will be showered with the MonteCarlo specified \n" + \
                "     in the run_card.dat\n"

_launch_parser = misc.OptionParser(usage=_launch_usage)
_launch_parser.add_option("-f", "--force", default=False, action='store_true',
                                help="Use the card present in the directory for the launch, without editing them")
_launch_parser.add_option("-c", "--cluster", default=False, action='store_true',
                            help="Submit the jobs on the cluster")
_launch_parser.add_option("-m", "--multicore", default=False, action='store_true',
                            help="Submit the jobs on multicore mode")
_launch_parser.add_option("-x", "--nocompile", default=False, action='store_true',
                            help="Skip compilation. Ignored if no executable is found")
_launch_parser.add_option("-r", "--reweightonly", default=False, action='store_true',
                            help="Skip integration and event generation, just run reweight on the" + \
                                 " latest generated event files (see list in SubProcesses/nevents_unweighted)")
_launch_parser.add_option("-p", "--parton", default=False, action='store_true',
                            help="Stop the run after the parton level file generation (you need " + \
                                    "to shower the file in order to get physical results)")
_launch_parser.add_option("-o", "--only_generation", default=False, action='store_true',
                            help="Skip grid set up, just generate events starting from " + \
                            "the last available results")
_launch_parser.add_option("-n", "--name", default=False, dest='run_name',
                            help="Provide a name to the run")
_launch_parser.add_option("-a", "--appl_start_grid", default=False, dest='appl_start_grid',
                            help="For use with APPLgrid only: start from existing grids")


_generate_events_usage = "generate_events [MODE] [options]\n" + \
                "-- execute aMC@NLO \n" + \
                "   MODE can be either LO, NLO, aMC@NLO or aMC@LO (if omitted, it is asked in a separate question)\n" + \
                "     If mode is set to LO/NLO, no event generation will be performed, but only the \n" + \
                "     computation of the total cross-section and the filling of parton-level histograms \n" + \
                "     specified in the DIRPATH/SubProcesses/madfks_plot.f file.\n" + \
                "     If mode is set to aMC@LO/aMC@NLO, after the cross-section computation, a .lhe \n" + \
                "     event file is generated which will be showered with the MonteCarlo specified \n" + \
                "     in the run_card.dat\n"

_generate_events_parser = misc.OptionParser(usage=_generate_events_usage)
_generate_events_parser.add_option("-f", "--force", default=False, action='store_true',
                                help="Use the card present in the directory for the generate_events, without editing them")
_generate_events_parser.add_option("-c", "--cluster", default=False, action='store_true',
                            help="Submit the jobs on the cluster")
_generate_events_parser.add_option("-m", "--multicore", default=False, action='store_true',
                            help="Submit the jobs on multicore mode")
_generate_events_parser.add_option("-x", "--nocompile", default=False, action='store_true',
                            help="Skip compilation. Ignored if no executable is found")
_generate_events_parser.add_option("-r", "--reweightonly", default=False, action='store_true',
                            help="Skip integration and event generation, just run reweight on the" + \
                                 " latest generated event files (see list in SubProcesses/nevents_unweighted)")
_generate_events_parser.add_option("-p", "--parton", default=False, action='store_true',
                            help="Stop the run after the parton level file generation (you need " + \
                                    "to shower the file in order to get physical results)")
_generate_events_parser.add_option("-o", "--only_generation", default=False, action='store_true',
                            help="Skip grid set up, just generate events starting from " + \
                            "the last available results")
_generate_events_parser.add_option("-n", "--name", default=False, dest='run_name',
                            help="Provide a name to the run")



_calculate_xsect_usage = "calculate_xsect [ORDER] [options]\n" + \
                "-- calculate cross-section up to ORDER.\n" + \
                "   ORDER can be either LO or NLO (if omitted, it is set to NLO). \n"

_calculate_xsect_parser = misc.OptionParser(usage=_calculate_xsect_usage)
_calculate_xsect_parser.add_option("-f", "--force", default=False, action='store_true',
                                help="Use the card present in the directory for the launch, without editing them")
_calculate_xsect_parser.add_option("-c", "--cluster", default=False, action='store_true',
                            help="Submit the jobs on the cluster")
_calculate_xsect_parser.add_option("-m", "--multicore", default=False, action='store_true',
                            help="Submit the jobs on multicore mode")
_calculate_xsect_parser.add_option("-x", "--nocompile", default=False, action='store_true',
                            help="Skip compilation. Ignored if no executable is found")
_calculate_xsect_parser.add_option("-n", "--name", default=False, dest='run_name',
                            help="Provide a name to the run")
_calculate_xsect_parser.add_option("-a", "--appl_start_grid", default=False, dest='appl_start_grid',
                            help="For use with APPLgrid only: start from existing grids")
_calculate_xsect_parser.add_option("-o", "--only_generation", default=False, action='store_true',
                            help="Skip grid set up, just generate events starting from " + \
                            "the last available results")

_shower_usage = 'shower run_name [options]\n' + \
        '-- do shower/hadronization on parton-level file generated for run run_name\n' + \
        '   all the information (e.g. number of events, MonteCarlo, ...\n' + \
        '   are directly read from the header of the event file\n'
_shower_parser = misc.OptionParser(usage=_shower_usage)
_shower_parser.add_option("-f", "--force", default=False, action='store_true',
                                help="Use the shower_card present in the directory for the launch, without editing")


