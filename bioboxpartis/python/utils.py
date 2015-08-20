""" A few utility functions. At the moment simply functions used in recombinator which do not
require member variables. """

import sys
import os
import re
import math
import glob
from collections import OrderedDict
import csv

from opener import opener

from Bio import SeqIO

#----------------------------------------------------------------------------------------
# NOTE I also have an eps defined in hmmwriter. Simplicity is the hobgoblin of... no, wait, that's just plain ol' stupid to have two <eps>s defined
eps = 1.0e-10  # if things that should be 1.0 are this close to 1.0, blithely keep on keepin on. kinda arbitrary, but works for the moment
def is_normed(probs, this_eps=eps):
    if hasattr(probs, 'keys'):  # if it's a dict, call yourself with a list of the dict's values
        return is_normed([val for key, val in probs.items()])
    elif hasattr(probs, '__getitem__'):  # if it's a list call yourself with their sum
        return is_normed(sum(probs))
    else:  # and if it's a float actually do what you're supposed to do
        return math.fabs(probs - 1.0) < this_eps

# ----------------------------------------------------------------------------------------
def get_arg_list(arg, intify=False):  # make lists from args that are passed as strings of colon-separated values
    if arg == None:
        return arg
    else:
        arglist = arg.strip().split(':')  # to allow ids with minus signs, need to add a space, which you then have to strip() off
        if intify:
            return [int(x) for x in arglist]
        else:
            return arglist

# # ----------------------------------------------------------------------------------------
# hackey_default_gene_versions = {'v':'IGHV3-23*04', 'd':'IGHD3-10*01', 'j':'IGHJ4*02_F'}
# ----------------------------------------------------------------------------------------
regions = ['v', 'd', 'j']
real_erosions = ['v_3p', 'd_5p', 'd_3p', 'j_5p']
effective_erosions = ['v_5p', 'j_3p']
boundaries = ('vd', 'dj')
humans = ('A', 'B', 'C')
nukes = ('A', 'C', 'G', 'T')
naivities = ['M', 'N']
conserved_codon_names = {'v':'cyst', 'd':'', 'j':'tryp'}
# Infrastrucure to allow hashing all the columns together into a dict key.
# Uses a tuple with the variables that are used to index selection frequencies
# NOTE fv and jf insertions are *effective* (not real) insertions between v or j and the framework. The allow query sequences that extend beyond the v or j regions
index_columns = ('v_gene', 'd_gene', 'j_gene', 'cdr3_length', 'v_5p_del', 'v_3p_del', 'd_5p_del', 'd_3p_del', 'j_5p_del', 'j_3p_del', 'fv_insertion', 'vd_insertion', 'dj_insertion', 'jf_insertion')
# not_used_for_simulation = ('fv_insertion', 'jf_insertion', 'v_5p_del')
index_keys = {}
for i in range(len(index_columns)):  # dict so we can access them by name instead of by index number
    index_keys[index_columns[i]] = i

# ----------------------------------------------------------------------------------------
# Info specifying which parameters are assumed to correlate with which others. Taken from mutual
# information plot in bcellap repo

# key is parameter of interest, and associated list gives the parameters (other than itself) which are necessary to predict it
column_dependencies = {}
column_dependencies['v_gene'] = [] # NOTE v choice actually depends on everything... but not super strongly, so a.t.m. I ignore it
column_dependencies['v_5p_del'] = ['v_gene']
column_dependencies['v_3p_del'] = ['v_gene']
column_dependencies['d_gene'] = []
column_dependencies['d_5p_del'] = ['d_gene']  # NOTE according to the mebcell mutual information plot d_5p_del is also correlated to d_3p_del (but we have no way to model that a.t.m. in the hmm)
column_dependencies['d_3p_del'] = ['d_gene']  # NOTE according to the mebcell mutual information plot d_3p_del is also correlated to d_5p_del (but we have no way to model that a.t.m. in the hmm)
column_dependencies['j_gene'] = []
column_dependencies['j_5p_del'] = ['j_gene']  # NOTE mebcell plot showed this correlation as being small, but I'm adding it here for (a possibly foolish) consistency
column_dependencies['j_3p_del'] = ['j_gene']
column_dependencies['fv_insertion'] = []
column_dependencies['vd_insertion'] = ['d_gene']
column_dependencies['dj_insertion'] = ['j_gene']
column_dependencies['jf_insertion'] = []

# column_dependencies['vd_insertion_content'] = []
# column_dependencies['dj_insertion_content'] = []

# tuples with the column and its dependencies mashed together
# (first entry is the column of interest, and it depends upon the following entries)
column_dependency_tuples = []
for column, deps in column_dependencies.iteritems():
    tmp_list = [column]
    tmp_list.extend(deps)
    column_dependency_tuples.append(tuple(tmp_list))

def get_parameter_fname(column=None, deps=None, column_and_deps=None):
    """ return the file name in which we store the information for <column>. Either pass in <column> and <deps> *or* <column_and_deps> """
    if column == 'all':
        return 'all-probs.csv'
    if column_and_deps == None:
        column_and_deps = [column]
        column_and_deps.extend(deps)
    outfname = 'probs.csv'
    for ic in column_and_deps:
        outfname = ic + '-' + outfname
    return outfname

# ----------------------------------------------------------------------------------------
# bash color codes
Colors = {}
Colors['head'] = '\033[95m'
Colors['bold'] = '\033[1m'
Colors['purple'] = '\033[95m'
Colors['blue'] = '\033[94m'
Colors['green'] = '\033[92m'
Colors['yellow'] = '\033[93m'
Colors['red'] = '\033[91m'
Colors['end'] = '\033[0m'

def color(col, seq):
    assert col in Colors
    return Colors[col] + seq + Colors['end']

# ----------------------------------------------------------------------------------------
def color_mutants(ref_seq, seq, print_result=False, extra_str='', ref_label='', post_str=''):
    assert len(ref_seq) == len(seq)
    return_str = ''
    for inuke in range(len(seq)):
        if inuke >= len(ref_seq) or seq[inuke] == ref_seq[inuke]:
            return_str += seq[inuke]
        else:
            return_str += color('red', seq[inuke])
    if print_result:
        print '%s%s%s' % (extra_str, ref_label, ref_seq)
        print '%s%s%s%s' % (extra_str, ' '*len(ref_label), return_str, post_str)
    return return_str

# ----------------------------------------------------------------------------------------
def color_gene(gene):
    """ color gene name (and remove extra characters), eg IGHV3-h*01 --> v 3-h 1 """
    return_str = gene[:3] + color('bold', color('red', gene[3])) + ' '  # add a space after
    n_version = gene[4 : gene.find('-')]
    n_subversion = gene[gene.find('-')+1 : gene.find('*')]
    if get_region(gene) == 'j':
        n_version = gene[4 : gene.find('*')]
        n_subversion = ''
        return_str += color('purple', n_version)
    else:
        return_str += color('purple', n_version) + '-' + color('purple', n_subversion)

    if gene.find('*') != -1:
        allele_end = gene.find('_')
        if allele_end < 0:
            allele_end = len(gene)
        allele = gene[gene.find('*')+1 : allele_end]
        return_str += '*' + color('yellow', allele)
        if '_' in gene:  # _F or _P in j gene names
            return_str += gene[gene.find('_') :]

    # now remove extra characters
    return_str = return_str.replace('IGH','  ').lower()
    return_str = return_str.replace('*',' ')
    return return_str

#----------------------------------------------------------------------------------------
def int_to_nucleotide(number):
    """ Convert between (0,1,2,3) and (A,C,G,T) """
    if number == 0:
        return 'A'
    elif number == 1:
        return 'C'
    elif number == 2:
        return 'G'
    elif number == 3:
        return 'T'
    else:
        print 'ERROR nucleotide number not in [0,3]'
        sys.exit()

# ----------------------------------------------------------------------------------------                    
def check_conserved_cysteine(seq, cyst_position, debug=False, extra_str=''):
    """ Ensure there's a cysteine at <cyst_position> in <seq>. """
    if len(seq) < cyst_position+3:
        if debug:
            print '%sERROR seq not long enough in cysteine checker %d %s' % (extra_str, cyst_position, seq)
        assert False
    cyst_word = str(seq[cyst_position:cyst_position+3])
    if cyst_word != 'TGT' and cyst_word != 'TGC':
        if debug:
            print '%sERROR cysteine in v is messed up: %s (%s %d)' % (extra_str, cyst_word, seq, cyst_position)
        assert False

# ----------------------------------------------------------------------------------------
def check_conserved_tryptophan(seq, tryp_position, debug=False, extra_str=''):
    """ Ensure there's a tryptophan at <tryp_position> in <seq>. """
    if len(seq) < tryp_position+3:
        if debug:
            print '%sERROR seq not long enough in tryp checker %d %s' % (extra_str, tryp_position, seq)
        assert False
    tryp_word = str(seq[tryp_position:tryp_position+3])
    if tryp_word != 'TGG':
        if debug:
            print '%sERROR tryptophan in j is messed up: %s (%s %d)' % (extra_str, tryp_word, seq, tryp_position)
        assert False

# ----------------------------------------------------------------------------------------
def check_both_conserved_codons(seq, cyst_position, tryp_position, debug=False, extra_str=''):
    """ Double check that we conserved the cysteine and the tryptophan. """
    check_conserved_cysteine(seq, cyst_position, debug, extra_str=extra_str)
    check_conserved_tryptophan(seq, tryp_position, debug, extra_str=extra_str)

# ----------------------------------------------------------------------------------------
def are_conserved_codons_screwed_up(reco_event):
    """ Version that checks all the final seqs in reco_event.

    Returns True if codons are screwed up, or if no sequences have been added.
    """
    if len(reco_event.final_seqs) == 0:
        return True
    for seq in reco_event.final_seqs:
        try:
            check_both_conserved_codons(seq, reco_event.final_cyst_position, reco_event.final_tryp_position)
        except AssertionError:
            return True

    return False

#----------------------------------------------------------------------------------------
def check_for_stop_codon(seq, cyst_position, debug=False):
    """ make sure there is no in-frame stop codon, where frame is inferred from <cyst_position> """
    assert cyst_position < len(seq)
    # jump leftward in steps of three until we reach the start of the sequence
    ipos = cyst_position
    while ipos > 2:
        ipos -= 3
    # ipos should now bet the index of the start of the first complete codon
    while ipos + 2 < len(seq):  # then jump forward in steps of three bases making sure none of them are stop codons
        codon = seq[ipos:ipos+3]
        if codon == 'TAG' or codon == 'TAA' or codon == 'TGA':
            if debug:
                print '      ERROR stop codon %s at %d in %s' % (codon, ipos, seq)
            assert False
        ipos += 3

#----------------------------------------------------------------------------------------
def is_position_protected(protected_positions, prospective_position):
    """ Would a mutation at <prospective_position> screw up a protected codon? """
    for position in protected_positions:
        if (prospective_position == position or
            prospective_position == (position + 1) or
            prospective_position == (position + 2)):
            return True
    return False

#----------------------------------------------------------------------------------------
def would_erode_conserved_codon(reco_event):
    """ Would any of the erosion <lengths> delete a conserved codon? """
    lengths = reco_event.erosions
    # check conserved cysteine
    if len(reco_event.seqs['v']) - lengths['v_3p'] <= reco_event.cyst_position + 2:
        print '      about to erode cysteine (%d), try again' % lengths['v_3p']
        return True  # i.e. it *would* screw it up
    # check conserved tryptophan
    if lengths['j_5p'] - 1 >= reco_event.tryp_position:
        print '      about to erode tryptophan (%d), try again' % lengths['j_5p']
        return True

    return False  # *whew*, it won't erode either of 'em

#----------------------------------------------------------------------------------------
def is_erosion_longer_than_seq(reco_event):
    """ Are any of the proposed erosion <lengths> longer than the seq to be eroded? """
    lengths = reco_event.erosions
    if lengths['v_3p'] > len(reco_event.seqs['v']):  # NOTE not actually possible since we already know we didn't erode the cysteine
        print '      v_3p erosion too long (%d)' % lengths['v_3p']
        return True
    if lengths['d_5p'] + lengths['d_3p'] > len(reco_event.seqs['d']):
        print '      d erosions too long (%d)' % (lengths['d_5p'] + lengths['d_3p'])
        return True
    if lengths['j_5p'] > len(reco_event.seqs['j']):  # NOTE also not possible for the same reason
        print '      j_5p erosion too long (%d)' % lengths['j_5p']
        return True
    return False

#----------------------------------------------------------------------------------------
def find_tryp_in_joined_seq(gl_tryp_position_in_j, v_seq, vd_insertion, d_seq, dj_insertion, j_seq, j_erosion, debug=False):
    """ Find the <end> tryptophan in a joined sequence.

    Given local tryptophan position in the j region, figure
    out what position it's at in the final sequence.
    NOTE gl_tryp_position_in_j is the position *before* the j was eroded,
    but this fcn assumes that the j *has* been eroded.
    also NOTE <[vdj]_seq> are assumed to already be eroded
    """
    if debug:
        print 'checking tryp with: %s, %d - %d = %d' % (j_seq, gl_tryp_position_in_j, j_erosion, gl_tryp_position_in_j - j_erosion)
    check_conserved_tryptophan(j_seq, gl_tryp_position_in_j - j_erosion)  # make sure tryp is where it's supposed to be
    length_to_left_of_j = len(v_seq + vd_insertion + d_seq + dj_insertion)
    if debug:
        print '  finding tryp position as'
        print '    length_to_left_of_j = len(v_seq + vd_insertion + d_seq + dj_insertion) = %d + %d + %d + %d' % (len(v_seq), len(vd_insertion), len(d_seq), len(dj_insertion))
        print '    result = gl_tryp_position_in_j - j_erosion + length_to_left_of_j = %d - %d + %d = %d' % (gl_tryp_position_in_j, j_erosion, length_to_left_of_j, gl_tryp_position_in_j - j_erosion + length_to_left_of_j)
    return gl_tryp_position_in_j - j_erosion + length_to_left_of_j

# ----------------------------------------------------------------------------------------
def is_mutated(original, final, n_muted=-1, n_total=-1):
    n_total += 1
    return_str = final
    if original != final:
        return_str = color('red', final)
        n_muted += 1
    return return_str, n_muted, n_total

# ----------------------------------------------------------------------------------------
def get_v_5p_del(original_seqs, line):
    # deprecated
    assert False  # this method will no longer work when I need to get v left *and* j right 'deletions'
    original_length = len(original_seqs['v']) + len(original_seqs['d']) + len(original_seqs['j'])
    total_deletion_length = int(line['v_3p_del']) + int(line['d_5p_del']) + int(line['d_3p_del']) + int(line['j_5p_del'])
    total_insertion_length = len(line['vd_insertion']) + len(line['dj_insertion'])
    return original_length - total_deletion_length + total_insertion_length - len(line['seq'])

# ----------------------------------------------------------------------------------------
def get_reco_event_seqs(germlines, line, original_seqs, lengths, eroded_seqs):
    """
    get original and eroded germline seqs
    NOTE does not modify line
    """
    for region in regions:
        del_5p = int(line[region + '_5p_del'])
        del_3p = int(line[region + '_3p_del'])
        original_seqs[region] = germlines[region][line[region + '_gene']]
        lengths[region] = len(original_seqs[region]) - del_5p - del_3p
        # assert del_5p + lengths[region] != 0
        eroded_seqs[region] = original_seqs[region][del_5p : del_5p + lengths[region]]

# ----------------------------------------------------------------------------------------
def get_conserved_codon_position(cyst_positions, tryp_positions, region, gene, all_glbounds, all_qrbounds):
    """
    Find location of the conserved cysteine/tryptophan in a query sequence given a germline match which is specified by
    its germline bounds <glbounds> and its bounds in the query sequence <qrbounds>
    """
    # NOTE see add_cdr3_info -- they do similar things, but start from different information
    if region == 'v':
        gl_pos = cyst_positions[gene]['cysteine-position']  # germline cysteine position
    elif region == 'j':
        gl_pos = int(tryp_positions[gene])
    else:
        return -1

    if gl_pos == None:
        print 'ERROR none gl_pos for %s ' % gene
        sys.exit()

    glbounds = all_glbounds[gene]
    qrbounds = all_qrbounds[gene]
    query_pos = gl_pos - glbounds[0] + qrbounds[0]
    return query_pos

# ----------------------------------------------------------------------------------------
def add_cdr3_info(cyst_positions, tryp_positions, line, eroded_seqs, debug=False):
    """
    Add the cyst_position, tryp_position, and cdr3_length to <line> based on the information already in <line>.
    If info is already there, make sure it's the same as what we calculate here
    """
    # NOTE see get_conserved_codon_position -- they do similar things, but start from different information
    eroded_gl_cpos = cyst_positions[line['v_gene']]['cysteine-position']  - int(line['v_5p_del']) + len(line['fv_insertion'])  # cysteine position in eroded germline sequence. EDIT darn, actually you *don't* want to subtract off the v left deletion, because that (deleted) base is presumably still present in the query sequence
    # if debug:
    #     print '  cysteine: cpos - v_5p_del + fv_insertion = %d - %d + %d = %d' % (cyst_positions[line['v_gene']]['cysteine-position'], int(line['v_5p_del']), len(line['fv_insertion']), eroded_gl_cpos)
    eroded_gl_tpos = int(tryp_positions[line['j_gene']]) - int(line['j_5p_del'])
    values = {}
    values['cyst_position'] = eroded_gl_cpos
    tpos_in_joined_seq = eroded_gl_tpos + len(line['fv_insertion']) + len(eroded_seqs['v']) + len(line['vd_insertion']) + len(eroded_seqs['d']) + len(line['dj_insertion'])
    values['tryp_position'] = tpos_in_joined_seq
    values['cdr3_length'] = tpos_in_joined_seq - eroded_gl_cpos + 3

    for key, val in values.items():
        if key in line:
            if int(line[key]) != int(val):
                print 'ERROR', key, 'from line:', line[key], 'not equal to', val
                assert False
        else:
            line[key] = val
    
    try:
        check_conserved_cysteine(line['fv_insertion'] + eroded_seqs['v'], eroded_gl_cpos, debug=debug, extra_str='      ')
        check_conserved_tryptophan(eroded_seqs['j'], eroded_gl_tpos, debug=debug, extra_str='      ')
    except AssertionError:
        if debug:
            print '    bad codon, setting cdr3_length to -1'
        line['cdr3_length'] = -1

# ----------------------------------------------------------------------------------------
def get_full_naive_seq(germlines, line):  #, restrict_to_region=''):
    for erosion in real_erosions + effective_erosions:
        if line[erosion + '_del'] < 0:
            print 'ERROR %s less than zero %d' % (erosion, line[erosion + '_del'])
        assert line[erosion + '_del'] >= 0
    original_seqs = {}  # original (non-eroded) germline seqs
    lengths = {}  # length of each match (including erosion)
    eroded_seqs = {}  # eroded germline seqs
    get_reco_event_seqs(germlines, line, original_seqs, lengths, eroded_seqs)
    # if restrict_to_region == '':
    return line['fv_insertion'] + eroded_seqs['v'] + line['vd_insertion'] + eroded_seqs['d'] + line['dj_insertion'] + eroded_seqs['j'] + line['jf_insertion']
    # else:
    # return eroded_seqs[restrict_to_region]

# ----------------------------------------------------------------------------------------
def get_regional_naive_seq_bounds(return_reg, germlines, line, subtract_unphysical_erosions=True):
    # NOTE it's kind of a matter of taste whether unphysical deletions (v left and j right) should be included in the 'naive sequence'.
    # Unless <subtract_unphysical_erosions>, here we assume the naive sequence has *no* unphysical deletions

    original_seqs = {}  # original (non-eroded) germline seqs
    lengths = {}  # length of each match (including erosion)
    eroded_seqs = {}  # eroded germline seqs
    get_reco_event_seqs(germlines, line, original_seqs, lengths, eroded_seqs)

    start, end = {}, {}
    start['v'] = int(line['v_5p_del'])
    end['v'] = start['v'] + len(line['fv_insertion'] + eroded_seqs['v'])  # base just after the end of v
    start['d'] = end['v'] + len(line['vd_insertion'])
    end['d'] = start['d'] + len(eroded_seqs['d'])
    start['j'] = end['d'] + len(line['dj_insertion'])
    end['j'] = start['j'] + len(eroded_seqs['j'] + line['jf_insertion'])

    if subtract_unphysical_erosions:
        for tmpreg in regions:
            start[tmpreg] -= int(line['v_5p_del'])
            end[tmpreg] -= int(line['v_5p_del'])
        # end['j'] -= line['j_3p_del']  # ARG.ARG.ARG

    # for key, val in line.items():
    #     print key, val
    for chkreg in regions:
        # print chkreg, start[chkreg], end[chkreg]
        assert start[chkreg] >= 0
        assert end[chkreg] >= 0
        assert end[chkreg] >= start[chkreg]
    # print end['j'], len(line['seq']), line['v_5p_del'], line['j_3p_del']
    assert end['j'] == len(line['seq'])

    return (start[return_reg], end[return_reg])

# ----------------------------------------------------------------------------------------
def add_match_info(germlines, line, cyst_positions, tryp_positions, debug=False):
    """
    add to <line> the query match seqs (sections of the query sequence that are matched to germline) and their corresponding germline matches.

    """

    original_seqs = {}  # original (non-eroded) germline seqs
    lengths = {}  # length of each match (including erosion)
    eroded_seqs = {}  # eroded germline seqs
    get_reco_event_seqs(germlines, line, original_seqs, lengths, eroded_seqs)
    add_cdr3_info(cyst_positions, tryp_positions, line, eroded_seqs, debug=debug)  # add cyst and tryp positions, and cdr3 length

    # add the <eroded_seqs> to <line> so we can find them later
    for region in regions:
        line[region + '_gl_seq'] = eroded_seqs[region]

    # the sections of the query sequence which are assigned to each region
    v_start = len(line['fv_insertion'])
    d_start = v_start + len(eroded_seqs['v']) + len(line['vd_insertion'])
    j_start = d_start + len(eroded_seqs['d']) + len(line['dj_insertion'])
    line['v_qr_seq'] = line['seq'][v_start : v_start + len(eroded_seqs['v'])]
    line['d_qr_seq'] = line['seq'][d_start : d_start + len(eroded_seqs['d'])]
    line['j_qr_seq'] = line['seq'][j_start : j_start + len(eroded_seqs['j'])]

    # if line['cdr3_length'] == -1:
    #     print '      ERROR %s failed to add match info' % ' '.join([str(i) for i in ids])

# ----------------------------------------------------------------------------------------
def print_reco_event(germlines, line, one_line=False, extra_str='', return_string=False, label=''):
    """ Print ascii summary of recombination event and mutation.

    If <one_line>, then only print out the final_seq line.
    """
    
    v_5p_del = int(line['v_5p_del'])
    v_3p_del = int(line['v_3p_del'])
    d_5p_del = int(line['d_5p_del'])
    d_3p_del = int(line['d_3p_del'])
    j_5p_del = int(line['j_5p_del'])
    j_3p_del = int(line['j_3p_del'])

    original_seqs = {}  # original (non-eroded) germline seqs
    lengths = {}  # length of each match (including erosion)
    eroded_seqs = {}  # eroded germline seqs
    get_reco_event_seqs(germlines, line, original_seqs, lengths, eroded_seqs)

    germline_v_end = len(line['fv_insertion']) + len(original_seqs['v']) - v_5p_del - 1  # position in the query sequence at which we find the last base of the v match.
                                                                                         # NOTE we subtract off the v_5p_del because we're *not* adding dots for that deletion (it's just too long)
    germline_d_start = len(line['fv_insertion']) + lengths['v'] + len(line['vd_insertion']) - d_5p_del
    germline_d_end = germline_d_start + len(original_seqs['d'])
    germline_j_start = germline_d_end + 1 - d_3p_del + len(line['dj_insertion']) - j_5p_del

    # build up the query sequence line, including colors for mutations and conserved codons
    final_seq = ''
    n_muted, n_total = 0, 0
    j_right_extra = ''  # portion of query sequence to right of end of the j match
    for inuke in range(len(line['seq'])):
        ilocal = inuke
        new_nuke = ''
        if ilocal < len(line['fv_insertion']):  # haven't got to start of v match yet, so just add on the query seq nuke
            new_nuke = line['seq'][inuke]
        else:
            ilocal -= len(line['fv_insertion'])
            if ilocal < lengths['v']:
                new_nuke, n_muted, n_total = is_mutated(eroded_seqs['v'][ilocal], line['seq'][inuke], n_muted, n_total)
            else:
                ilocal -= lengths['v']
                if ilocal < len(line['vd_insertion']):
                    new_nuke, n_muted, n_total = is_mutated(line['vd_insertion'][ilocal], line['seq'][inuke], n_muted, n_total)
                else:
                    ilocal -= len(line['vd_insertion'])
                    if ilocal < lengths['d']:
                        new_nuke, n_muted, n_total = is_mutated(eroded_seqs['d'][ilocal], line['seq'][inuke], n_muted, n_total)
                    else:
                        ilocal -= lengths['d']
                        if ilocal < len(line['dj_insertion']):
                            new_nuke, n_muted, n_total = is_mutated(line['dj_insertion'][ilocal], line['seq'][inuke], n_muted, n_total)
                        else:
                            ilocal -= len(line['dj_insertion'])
                            if ilocal < lengths['j']:
                                new_nuke, n_muted, n_total = is_mutated(eroded_seqs['j'][ilocal], line['seq'][inuke], n_muted, n_total)
                            else:
                                new_nuke, n_muted, n_total = line['seq'][inuke], n_muted, n_total+1
                                j_right_extra += ' '

        if 'cyst_position' in line and 'tryp_position' in line:
            for pos in (line['cyst_position'], line['tryp_position']):  # reverse video for the conserved codon positions
                # adjusted_pos = pos - v_5p_del  # adjust positions to allow for reads not extending all the way to left side of v
                adjusted_pos = pos  # don't need to subtract it for smith-waterman stuff... gr, need to make it general
                if inuke >= adjusted_pos and inuke < adjusted_pos+3:
                    new_nuke = '\033[7m' + new_nuke + '\033[m'

        final_seq += new_nuke

    # check if there isn't enough space for dots in the vj line
    no_space = False
    interior_length = len(line['vd_insertion']) + len(eroded_seqs['d']) + len(line['dj_insertion'])  # length of the portion of the vj line that is normally taken up by dots (and spaces)
    if v_3p_del + j_5p_del > interior_length:
        no_space = True

    if no_space:
        v_3p_del_str = '.' + str(v_3p_del) + '.'
        j_5p_del_str = '.' + str(j_5p_del) + '.'
        extra_space_because_of_fixed_nospace = max(0, interior_length - len(v_3p_del_str + j_5p_del_str))
        if len(v_3p_del_str + j_5p_del_str) <= interior_length:  # ok, we've got space now
            no_space = False
    else:
        v_3p_del_str = '.'*v_3p_del
        j_5p_del_str = '.'*j_5p_del
        extra_space_because_of_fixed_nospace = 0

    eroded_seqs_dots = {}
    eroded_seqs_dots['v'] = eroded_seqs['v'] + v_3p_del_str
    eroded_seqs_dots['d'] = '.'*d_5p_del + eroded_seqs['d'] + '.'*d_3p_del
    eroded_seqs_dots['j'] = j_5p_del_str + eroded_seqs['j'] + '.'*j_3p_del

    v_5p_del_str = '.'*v_5p_del
    if v_5p_del > 50:
        v_5p_del_str = '...' + str(v_5p_del) + '...'

    insert_line = ' '*len(line['fv_insertion']) + ' '*lengths['v']
    insert_line += ' '*len(v_5p_del_str)
    insert_line += line['vd_insertion']
    insert_line += ' ' * lengths['d']
    insert_line += line['dj_insertion']
    insert_line += ' ' * lengths['j']
    insert_line += j_right_extra
    insert_line += ' ' * j_3p_del  # no damn idea why these need to be commented out for some cases in the igblast parser...
    # insert_line += ' '*len(line['jf_insertion'])

    d_line = ' ' * germline_d_start
    d_line += ' '*len(v_5p_del_str)
    d_line += eroded_seqs_dots['d']
    d_line += ' ' * (len(original_seqs['j']) - j_5p_del - j_3p_del + len(line['dj_insertion']) - d_3p_del)
    d_line += j_right_extra
    d_line += ' ' * j_3p_del
    # d_line += ' '*len(line['jf_insertion'])

    vj_line = ' ' * len(line['fv_insertion'])
    vj_line += v_5p_del_str
    vj_line += eroded_seqs_dots['v'] + '.'*extra_space_because_of_fixed_nospace
    vj_line += ' ' * (germline_j_start - germline_v_end - 2)
    vj_line += eroded_seqs_dots['j']
    vj_line += j_right_extra
    # vj_line += ' '*len(line['jf_insertion'])

    if len(insert_line) != len(d_line) or len(insert_line) != len(vj_line):
        # print '\nERROR lines unequal lengths in event printer -- insertions %d d %d vj %d' % (len(insert_line), len(d_line), len(vj_line)),
        # assert no_space
        if not no_space:
            print 'ERROR no space'
        # print ' ...but we\'re out of space so it\'s expected'

    out_str_list = []
    # insert, d, and vj lines
    if not one_line:
        out_str_list.append('%s    %s   inserts\n' % (extra_str, insert_line))
        if label != '':
            out_str_list[-1] = extra_str + label + out_str_list[-1][len(extra_str + label) :]
        out_str_list.append('%s    %s   %s\n' % (extra_str, d_line, color_gene(line['d_gene'])))
        out_str_list.append('%s    %s   %s,%s\n' % (extra_str, vj_line, color_gene(line['v_gene']), color_gene(line['j_gene'])))

    # then query sequence
    final_seq = ' '*len(v_5p_del_str) + final_seq
    out_str_list.append('%s    %s%s' % (extra_str, final_seq, ' ' * j_3p_del))
    # and finally some extra info
    out_str_list.append('   muted: %4.2f' % (float(n_muted) / n_total))
    if 'score' in line:
        out_str_list.append('  score: %s' % line['score'])
    if 'cdr3_length' in line:
        out_str_list.append('   cdr3: %d' % int(line['cdr3_length']))
    out_str_list.append('\n')

    if return_string:
        return ''.join(out_str_list)
    else:
        print ''.join(out_str_list),

    assert '.' not in line['seq']  # make sure I'm no longer altering line['seq']
    assert ' ' not in line['seq']
    assert '[' not in line['seq']
    assert ']' not in line['seq']

#----------------------------------------------------------------------------------------
def sanitize_name(name):
    """ Replace characters in gene names that make crappy filenames. """
    saniname = name.replace('*', '_star_')
    saniname = saniname.replace('/', '_slash_')
    return saniname

#----------------------------------------------------------------------------------------
def unsanitize_name(name):
    """ Re-replace characters in gene names that make crappy filenames. """
    unsaniname = name.replace('_star_', '*')
    unsaniname = unsaniname.replace('_slash_', '/')
    return unsaniname

#----------------------------------------------------------------------------------------
def read_germlines(data_dir, remove_N_nukes=False):  #, remove_fp=False, add_fp=False, remove_N_nukes=False):
    """ <remove_fp> sometimes j names have a redundant _F or _P appended to their name. Set to True to remove this """
    print 'read gl from', data_dir
    germlines = {}
    for region in regions:
        germlines[region] = OrderedDict()
        for seq_record in SeqIO.parse(data_dir + '/igh'+region+'.fasta', "fasta"):
            gene_name = seq_record.name
            # if remove_fp and region == 'j':
            #     gene_name = gene_name[:-2]
            # if add_fp and region == 'j':
            #     if 'P' in gene_name:
            #         gene_name = gene_name + '_P'
            #     else:
            #         gene_name = gene_name + '_F'
            seq_str = str(seq_record.seq)
            if remove_N_nukes and 'N' in seq_str:
                print 'WARNING replacing N with A in germlines'
                seq_str = seq_str.replace('N', 'A')
            germlines[region][gene_name] = seq_str
    return germlines

# ----------------------------------------------------------------------------------------
def get_region(gene_name):
    """ return v, d, or j of gene"""
    try:
        assert 'IGH' in gene_name
        region = gene_name[3:4].lower()
        assert region in regions
        return region
    except:
        print 'ERROR faulty gene name %s ' % gene_name
        assert False
# ----------------------------------------------------------------------------------------
def maturity_to_naivety(maturity):
    if maturity == 'memory':
        return 'M'
    elif maturity == 'naive':
        return 'N'
    else:
        assert False

# # ----------------------------------------------------------------------------------------
# def split_gene_name(name):
#     """
#     split name into region, version, allele, etc.
#     e.g. IGHD7-27*01 --> {'region':'d', 'version':7, 'subversion':27, 'allele':1}
#     """
#     return_vals = {}
#     return_vals['region'] = get_region(name)
#     assert name.count('-') == 1
#     return_vals['version'] = name[4 : name.find('-')]
    
#     assert name.count('*') == 1
    

# ----------------------------------------------------------------------------------------
def are_alleles(gene1, gene2):
    """
    Return true if gene1 and gene2 are alleles of the same gene version.
    Assumes they're alleles if everything left of the asterisk is the same, and everything more than two to the right of the asterisk is the same.
    """
    # gene1 = apply_renaming_scheme(gene1)
    # gene2 = apply_renaming_scheme(gene2)

    left_str_1 = gene1[0 : gene1.find('*')]
    left_str_2 = gene2[0 : gene1.find('*')]
    right_str_1 = gene1[gene1.find('*')+3 :]
    right_str_2 = gene2[gene1.find('*')+3 :]
    return left_str_1 == left_str_2 and right_str_1 == right_str_2

# ----------------------------------------------------------------------------------------
def are_same_primary_version(gene1, gene2):
    """
    Return true if the bit up to the dash is the same.
    There's probably a real name for that bit.
    """
    str_1 = gene1[0 : gene1.find('-')]
    str_2 = gene2[0 : gene2.find('-')]
    return str_1 == str_2

# ----------------------------------------------------------------------------------------
def read_overall_gene_probs(indir, only_gene='', normalize=True):
    """
    Return the observed counts/probabilities of choosing each gene version.
    If <normalize> then return probabilities
    If <only_gene> is specified, just return the prob/count for that gene
    """
    counts = { region:{} for region in regions }
    probs = { region:{} for region in regions }
    for region in regions:
        total = 0
        with opener('r')(indir + '/' + region + '_gene-probs.csv') as infile:  # NOTE note this ignores correlations... which I think is actually ok, but it wouldn't hurt to think through it again at some point
            reader = csv.DictReader(infile)
            for line in reader:
                line_count = int(line['count'])
                gene = line[region + '_gene']
                total += line_count
                if gene not in counts[region]:
                    counts[region][gene] = 0
                counts[region][gene] += line_count
        if total < 1:
            assert total == 0
            print 'ERROR zero counts in %s' % indir + '/' + region + '_gene-probs.csv'
            assert False
        for gene in counts[region]:
            probs[region][gene] = float(counts[region][gene]) / total

    if only_gene not in counts[get_region(only_gene)]:
        print '      WARNING %s not found in overall gene probs, returning zero' % only_gene
        if normalize:
            return 0.0
        else:
            return 0

    if only_gene == '':
        if normalize:
            return probs
        else:
            return counts
    else:
        if normalize:
            return probs[get_region(only_gene)][only_gene]
        else:
            return counts[get_region(only_gene)][only_gene]

# ----------------------------------------------------------------------------------------
def find_replacement_genes(indir, min_counts, gene_name=None, single_gene=False, debug=False, all_from_region=''):
    if gene_name != None:
        assert all_from_region == ''
        region = get_region(gene_name)
    else:
        assert all_from_region in regions
        assert single_gene == False
        assert min_counts == -1
        region = all_from_region
    lists = OrderedDict()  # we want to try alleles first, then primary versions, then everything and it's mother
    lists['allele'] = []  # list of genes that are alleles of <gene_name>
    lists['primary_version'] = []  # same primary version as <gene_name>
    lists['all'] = []  # give up and return everything
    with opener('r')(indir + '/' + region + '_gene-probs.csv') as infile:  # NOTE note this ignores correlations... which I think is actually ok, but it wouldn't hurt to think through it again at some point
        reader = csv.DictReader(infile)
        for line in reader:
            gene = line[region + '_gene']
            count = int(line['count'])
            vals = {'gene':gene, 'count':count}
            if all_from_region == '':
                if are_alleles(gene, gene_name):
                    lists['allele'].append(vals)
                if are_same_primary_version(gene, gene_name):
                    lists['primary_version'].append(vals)
            lists['all'].append(vals)

    if single_gene:
        for list_type in lists:
            # return the first which has at least <min_counts> counts
            lists[list_type].sort(reverse=True, key=lambda vals: vals['count'])  # sort by score
            for vals in lists[list_type]:
                if vals['count'] >= min_counts:
                    if debug:
                        print '    return replacement %s %s' % (list_type, color_gene(vals['gene']))
                    return vals['gene']

        print 'ERROR didn\'t find any genes with at least %d for %s in %s' % (min_counts, gene_name, indir)
        assert False
    else:
        # return the whole list NOTE we're including here <gene_name>
        if all_from_region != '':
            return [vals['gene'] for vals in lists['all']]
        for list_type in lists:
            total_counts = sum([vals['count'] for vals in lists[list_type]])
            if total_counts >= min_counts:
                return_list = [vals['gene'] for vals in lists[list_type]]
                if debug:
                    print '      returning all %s for %s (%d genes, %d total counts)' % (list_type + 's', gene_name, len(return_list), total_counts)
                return return_list
            else:
                if debug:
                    print '      not enough counts in %s' % (list_type + 's')

        print 'ERROR couldn\'t find genes for %s in %s' % (gene_name, indir)
        assert False
    
    # print '    \nWARNING return default gene %s \'cause I couldn\'t find anything remotely resembling %s' % (color_gene(hackey_default_gene_versions[region]), color_gene(gene_name))
    # return hackey_default_gene_versions[region]


# ----------------------------------------------------------------------------------------
def get_hamming_distances(pairs):
    return_info = []
    for info in pairs:
        seq_a = info['seq_a']
        seq_b = info['seq_b']
        if True:  #self.args.truncate_pairs:  # chop off the left side of the longer one if they're not the same length
            min_length = min(len(seq_a), len(seq_b))
            seq_a = seq_a[-min_length : ]
            seq_b = seq_b[-min_length : ]
            chopped_off_left_sides = True
        mutation_frac = hamming(seq_a, seq_b) / float(len(seq_a))
        return_info.append({'id_a':info['id_a'], 'id_b':info['id_b'], 'score':mutation_frac})

    return return_info

# ----------------------------------------------------------------------------------------
def hamming(seq1, seq2):
    assert len(seq1) == len(seq2)
    total = 0
    for ch1, ch2 in zip(seq1, seq2):
        if ch1 != ch2:
            total += 1
    return total

# ----------------------------------------------------------------------------------------
def get_key(names):
    """
    Return a hashable combination of the two query names that's the same if we reverse their order.
    """
    return '.'.join(sorted([str(name) for name in names]))

# ----------------------------------------------------------------------------------------
def split_key(key):
    """ 
    Reverse the action of get_key(). 
    NOTE does not necessarily give a_ and b_ in the same order, though
    NOTE also that b_name may not be the same (if 0), and this just returns strings, even if original names were ints
    """
    # assert len(re.findall('.', key)) == 1  # make sure none of the keys had a dot in it
    return key.split('.')

# ----------------------------------------------------------------------------------------
def prep_dir(dirname, wildling=None, multilings=None):
    """ make <dirname> if it d.n.e., and if shell glob <wildling> is specified, remove existing files which are thereby matched """
    if os.path.exists(dirname):
        if wildling is not None:
            for fname in glob.glob(dirname + '/' + wildling):
                os.remove(fname)
        if multilings is not None:  # allow multiple file name suffixes
            for wild in multilings:
                for fname in glob.glob(dirname + '/' + wild):
                    os.remove(fname)
    else:
        os.makedirs(dirname)
    if wildling is not None or multilings is not None:
        if len([fname for fname in os.listdir(dirname) if os.path.isfile(dirname + '/' + fname)]) != 0:  # make sure there's no other files in the dir
            print 'ERROR files remain in',dirname,'despite wildling',
            if wildling != None:
                print wildling
            if multilings != None:
                print multilings
            assert False

# ----------------------------------------------------------------------------------------
def intify(info, splitargs=()):
    """ 
    Attempt to convert all the keys and values in <info> from str to int.
    The keys listed in <splitargs> will be split as colon-separated lists before intification.
    """
    for key, val in info.items():
        if key in splitargs:
            info[key] = info[key].split(':')
            for i in range(len(info[key])):
                try:
                    info[key][i] = int(info[key][i])
                except ValueError:
                    pass
        else:
            try:
                info[key] = int(val)
            except ValueError:
                pass

# ----------------------------------------------------------------------------------------
def merge_csvs(outfname, csv_list, cleanup=True):
    """ NOTE copy of merge_hmm_outputs in partitiondriver, I should really combine the two functions """
    header = None
    outfo = []
    # print 'merging'
    for infname in csv_list:
        # print '  ', infname
        workdir = os.path.dirname(infname)
        with opener('r')(infname) as sub_outfile:
            reader = csv.DictReader(sub_outfile)
            header = reader.fieldnames
            for line in reader:
                outfo.append(line)
        if cleanup:
            os.remove(infname)
            os.rmdir(workdir)

    if not os.path.exists(os.path.dirname(outfname)):
        os.makedirs(os.path.dirname(outfname))
    with opener('w')(outfname) as outfile:
        writer = csv.DictWriter(outfile, header)
        writer.writeheader()
        for line in outfo:
            writer.writerow(line)

# ----------------------------------------------------------------------------------------
def get_mutation_rate(germlines, line, restrict_to_region=''):
    naive_seq = get_full_naive_seq(germlines, line)  # NOTE this includes the fv and jf insertions
    muted_seq = line['seq']
    if restrict_to_region == '':  # NOTE this is very similar to code in performanceplotter. I should eventually cut it out of there and combine them, but I'm nervous a.t.m. because of all the complications there of having the true *and* inferred sequences so I'm punting
        mashed_naive_seq = ''
        mashed_muted_seq = ''
        for region in regions:  # can't use the full sequence because we have no idea what the mutations were in the inserts. So have to mash together the three regions
            bounds = get_regional_naive_seq_bounds(region, germlines, line, subtract_unphysical_erosions=True)
            mashed_naive_seq += naive_seq[bounds[0] : bounds[1]]
            mashed_muted_seq += muted_seq[bounds[0] : bounds[1]]
    else:
        bounds = get_regional_naive_seq_bounds(restrict_to_region, germlines, line, subtract_unphysical_erosions=True)
        naive_seq = naive_seq[bounds[0] : bounds[1]]
        muted_seq = muted_seq[bounds[0] : bounds[1]]


    # print 'restrict %s' % restrict_to_region
    # color_mutants(naive_seq, muted_seq, print_result=True, extra_str='  ')
    n_mutes = hamming(naive_seq, muted_seq)
    return float(n_mutes) / len(naive_seq)  # hamming() asserts they're the same length
