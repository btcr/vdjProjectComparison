#!/usr/bin/env python
# run sequence of commands to build models and plot performance
from subprocess import check_call
import os
import sys
import argparse
import multiprocessing

sys.path.insert(1, './python')
import utils

# ----------------------------------------------------------------------------------------
def run_command(cmd_str):
    print 'RUN', cmd + cmd_str
    check_call([cmd,] + cmd_str.split())

# ----------------------------------------------------------------------------------------
parser = argparse.ArgumentParser()
parser.add_argument('--label', required=True)  # label for this test run. e.g. results are written to dirs with this name
parser.add_argument('--n-queries', default='-1')  # label for this test run. e.g. results are written to dirs with this name
parser.add_argument('--n-sim-events', default='2000')  # NOTE still have to multiply by the number of leaves to get the number of sequences (default is 5, though, which'll give you 10k seqs)
parser.add_argument('--extra-args')  # args to pass on to commands (colon-separated) NOTE have to add space and quote like so: --extra-args ' __option' (NOTE replaces __ with --)
parser.add_argument('--datafname')
parser.add_argument('--simfname')
parser.add_argument('--plotdir', required=True)
parser.add_argument('--n-procs', type=int, default=max(1, multiprocessing.cpu_count() / 2))
all_actions = ('cache-data-parameters', 'simulate', 'cache-simu-parameters', 'plot-performance')
parser.add_argument('--actions', default=':'.join(all_actions), choices=all_actions, help='Colon-separated list of actions to perform')

args = parser.parse_args()
args.extra_args = utils.get_arg_list(args.extra_args)
args.actions = utils.get_arg_list(args.actions)

cmd = './bin/partis.py'
common_args = ' --n-procs ' + str(args.n_procs)
if args.extra_args != None:
    common_args += ' ' + ' '.join(args.extra_args).replace('__', '--')
if args.simfname == None:
    args.simfname = '_output/' + args.label + '/simu.csv'
param_dir = '_output/' + args.label

if 'cache-data-parameters' in args.actions:
    if args.datafname is None or not os.path.exists(args.datafname):
        raise Exception('ERROR datafname d.n.e.: ' + str(args.datafname))
    # cache parameters from data
    cmd_str = ' --action cache-parameters --seqfile ' + args.datafname + ' --is-data --skip-unproductive' + common_args
    cmd_str += ' --parameter-dir ' + param_dir + '/data'
    cmd_str += ' --plotdir ' + args.plotdir + '/params/data'
    cmd_str += ' --n-max-queries ' + args.n_queries
    run_command(cmd_str)

if 'simulate' in args.actions:
    # simulate based on data parameters
    cmd_str = ' --action simulate --outfname ' + args.simfname + common_args
    cmd_str += ' --parameter-dir ' + param_dir + '/data/hmm'
    cmd_str += ' --n-max-queries ' + str(args.n_sim_events)  # NOTE confusing using n-max-queries for both these thigns, sorry...
    run_command(cmd_str)

if 'cache-simu-parameters' in args.actions:
    # cache parameters from simulation
    cmd_str = ' --action cache-parameters --seqfile ' + args.simfname + common_args
    cmd_str += ' --parameter-dir ' + param_dir + '/simu'
    cmd_str += ' --plotdir ' + args.plotdir + '/params/simu'
    cmd_str += ' --n-max-queries ' + args.n_queries
    run_command(cmd_str)

if 'plot-performance' in args.actions:  # run point estimation on simulation
    cmd_str = ' --action run-viterbi --plot-performance --seqfile ' + args.simfname + common_args
    cmd_str += ' --parameter-dir ' + param_dir + '/simu/hmm'
    cmd_str += ' --plotdir ' + args.plotdir
    cmd_str += ' --n-max-queries ' + args.n_queries
    run_command(cmd_str)
