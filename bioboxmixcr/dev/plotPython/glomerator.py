import itertools
import os
import sys
import math
import csv
import time

import utils
from opener import opener
from clusterpath import ClusterPath

# ----------------------------------------------------------------------------------------
class Glomerator(object):
    # ----------------------------------------------------------------------------------------
    def __init__(self, reco_info=None):
        self.reco_info = reco_info
        self.paths = None

    # ----------------------------------------------------------------------------------------
    def naive_seq_glomerate(self, naive_seqs, n_clusters, debug=False):
        """ Perform hierarchical agglomeration (with naive hamming distance as the distance), stopping at <n_clusters> """
        start = time.time()
        clusters = [[names,] for names in naive_seqs.keys()]

        seqs_per_cluster = float(len(clusters)) / n_clusters
        max_per_cluster = int(math.ceil(seqs_per_cluster))
        if debug:
            print '  max %d per cluster' % max_per_cluster

        distances = {}  # cache the calculated fractional hamming distances

        # ----------------------------------------------------------------------------------------
        def get_clusters_to_merge():
            smallest_min_distance, clusters_to_merge = None, None
            n_skipped = 0
            for clust_a, clust_b in itertools.combinations(clusters, 2):  # find the two clusters which contain the pair of sequences which are closest in hamming fraction (skipping cluster pairs that would make a cluster that's too big)
                if len(clust_a) + len(clust_b) > max_per_cluster and not glomerate.merge_whatever_you_got:  # merged cluster would be too big, so look for smaller (albeit further-apart) things to merge
                    n_skipped += 1
                    continue
                min_distance = None  # find the smallest hamming distance between any two sequences in the two clusters
                for query_a in clust_a:
                    for query_b in clust_b:
                        joint_key = query_a + ';' + query_b  #';'.join([query_a, query_b])
                        if joint_key not in distances:
                            distances[joint_key] = utils.hamming_fraction(naive_seqs[query_a], naive_seqs[query_b])
                            distances[query_b + ';' + query_a] = distances[joint_key]  # also add with key in reverse order, in case we run into the pair that way later on
                        if min_distance is None or distances[joint_key] < min_distance:
                            min_distance = distances[joint_key]
                if smallest_min_distance is None or min_distance < smallest_min_distance:
                    smallest_min_distance = min_distance
                    clusters_to_merge = (clust_a, clust_b)

            if debug and n_skipped > 0:
                print '      skipped: %d ' % n_skipped

            return clusters_to_merge

        # ----------------------------------------------------------------------------------------
        def glomerate():
            if debug:
                print '    current ', ' '.join([str(len(cl)) for cl in clusters])
            clusters_to_merge = get_clusters_to_merge()
            if clusters_to_merge is None:  # if we didn't find a suitable pair
                if debug:
                    print '    didn\'t find shiznitz'
                glomerate.merge_whatever_you_got = True  # next time through, merge whatever's best regardless of size
            else:
                if debug:
                    print '    merging', len(clusters_to_merge[0]), len(clusters_to_merge[1])
                clusters.append(clusters_to_merge[0] + clusters_to_merge[1])
                clusters.remove(clusters_to_merge[0])
                clusters.remove(clusters_to_merge[1])

        # ----------------------------------------------------------------------------------------
        def homogenize():
            """ roughly equalize the cluster sizes """
            if debug:
                print '  homogenizing', len(clusters[0]), len(clusters[-1])  #, len(clusters[-1]) / 3.
                print '    before ', ' '.join([str(len(cl)) for cl in clusters])

            # move enough items from the end of the biggest cluster to the end of the smallest cluster that their sizes are equal (well, within one of each other, with the last cluster allowed to stay one bigger)
            n_to_keep_in_biggest_cluster = int(math.ceil(float(len(clusters[0]) + len(clusters[-1])) / 2))
            clusters[0] = clusters[0] + clusters[-1][n_to_keep_in_biggest_cluster : ]
            clusters[-1] = clusters[-1][ : n_to_keep_in_biggest_cluster]
            if debug:
                print '    after  ', ' '.join([str(len(cl)) for cl in clusters])
            clusters.sort(key=len)
            if debug:
                print '    sorted ', ' '.join([str(len(cl)) for cl in clusters])

        # ----------------------------------------------------------------------------------------
        # da bizniz
        glomerate.merge_whatever_you_got = False  # merge the best pair, even if together they'll be to big

        while len(clusters) > n_clusters:
            glomerate()
        
        if len(clusters) > 1:  # homogenize if partition is non-trivial
            clusters.sort(key=len)

            itries = 0
            # while len(clusters[0]) < 2./3 * len(clusters[-1]):  # and len(clusters[-1]) - len(clusters[0]) > 2:  # keep homogenizing while biggest cluster is more than 3/2 the size of the smallest (and while their sizes differ by more than 2)
            while float(len(clusters[-1])) / len(clusters[0]) > 1.1 and len(clusters[-1]) - len(clusters[0]) > 3:  # keep homogenizing while biggest cluster is more than 3/2 the size of the smallest (and while their sizes differ by more than 2)
                homogenize()
                itries += 1
                if itries > len(clusters):
                    if debug:
                        print '  too many homogenization tries'
                    break

        print '    divvy time: %.3f' % (time.time()-start)
        return clusters

    # ----------------------------------------------------------------------------------------
    def print_true_partition(self):
        print '  true partition'
        print '   clonal?   ids'
        true_partition = utils.get_true_partition(self.reco_info)
        for cluster in true_partition.values():
            same_event = utils.from_same_event(self.reco_info is None, self.reco_info, cluster)
            if same_event is None:
                same_event = -1
            print '     %d    %s' % (int(same_event), ':'.join([str(uid) for uid in cluster]))

    # ----------------------------------------------------------------------------------------
    def read_file_info(self, infname, n_paths, calc_adj_mi):
        paths = [None for _ in range(n_paths)]
        with opener('r')(infname) as csvfile:
            reader = csv.DictReader(csvfile)
            for line in reader:
                if line['partition'] == '':
                    raise Exception('ERROR null partition (one of the processes probably got passed zero sequences')  # shouldn't happen any more FLW
                uids = []
                for cluster in line['partition'].split(';'):
                    uids.append([unique_id for unique_id in cluster.split(':')])
                path_index = int(line['path_index'])
                if paths[path_index] is None:
                    paths[path_index] = ClusterPath(int(line['initial_path_index']))
                else:
                    assert paths[path_index].initial_path_index == int(line['initial_path_index'])
                n_procs = int(line['n_procs']) if 'n_procs' in line else 1
                logweight = float(line['logweight']) if 'logweight' in line else None
                adj_mi = -1
                if calc_adj_mi:
                    adj_mi = utils.mutual_information(uids, self.reco_info, debug=False) if self.reco_info is not None else -1
                paths[path_index].add_partition(uids, float(line['logprob']), n_procs=n_procs, logweight=logweight, adj_mi=adj_mi)

        for cp in paths:
            if cp is None:
                raise Exception('None type path read from %s' % infname)
            for ptn in cp.partitions:
                if len(ptn) == 0:
                    raise Exception('zero length partition read from %s' % infname)

        return paths

    # ----------------------------------------------------------------------------------------
    def merge_fileinfos(self, fileinfos, smc_particles, calc_adj_mi, previous_info=None, debug=False):
         # 'TODO not doing the combined conservative thing any more seems to have knocked down performance a bit EDIT nevermind, that seems to be a result of smc (presumably it was choosing very unlikely merges)'
        self.paths = [ClusterPath(None) for _ in range(smc_particles)]  # each path's initial_path_index is None since we're merging paths that, in general, have different initial path indices

        # DEAR FUTURE SELF this won't make any sense until you find that picture you took of the white board
        if previous_info is not None and smc_particles > 1:  # if we're doing smc, this has to happen *beforehand*, since the previous paths are separate for each process (cont'd at XX)
            assert len(previous_info) == len(fileinfos)  # both are the number of processes we're merging into one
            # TODO prevent this from adding duplicate adjacent partitions (well... not that important)
            if debug:
                print 'prepend previous history'
            for ifile in range(len(fileinfos)):
                if debug:
                    print 'ifile', ifile
                for ipath in range(smc_particles):
                    if debug:
                        print '  ipath', ipath
                        print '    before'
                        fileinfos[ifile][ipath].print_partitions(self.reco_info, one_line=True)
                    initial_path_index = fileinfos[ifile][ipath].initial_path_index  # which previous path are we hooking up to?
                    previous_path = previous_info[ifile][initial_path_index]
                    current_path = fileinfos[ifile][ipath]
                    # first_new_logprob = current_path.logprobs[0]
                    extended_path = ClusterPath(None)
                    for ip in range(len(previous_path.partitions)):
                        # if previous_path.logprobs[ip] >= first_new_logprob:  # skip the merges past which we rewound
                        #     continue
                        extended_path.add_partition(list(previous_path.partitions[ip]), previous_path.logprobs[ip], previous_path.n_procs[ip], logweight=previous_path.logweights[ip], adj_mi=previous_path.adj_mis[ip])
                    for ip in range(len(current_path.partitions)):
                        extended_path.add_partition(list(current_path.partitions[ip]), current_path.logprobs[ip], current_path.n_procs[ip], logweight=current_path.logweights[ip], adj_mi=current_path.adj_mis[ip])
                    fileinfos[ifile][ipath] = extended_path
                    fileinfos[ifile][ipath].set_synthetic_logweight_history(self.reco_info)  # need to multiply the combinatorical factors in the later partitions by the factors from the earlier partitions
                    if debug:
                        print '    after'
                        fileinfos[ifile][ipath].print_partitions(self.reco_info, one_line=True)

        # do the actual process-merging
        for ipath in range(smc_particles):

            if debug:
                print 'merge path %d from %d processes:' % (ipath, len(fileinfos))
                for ifile in range(len(fileinfos)):
                    fileinfos[ifile][ipath].print_partitions(self.reco_info, extrastr=('%d' % (ifile)), one_line=True)
                    print ''

            # merge all the steps in each path
            def last_one():
                last = True
                for ifile in range(len(fileinfos)):  # we're finished when all the files are out of glomeration steps (i.e. they all only have one [the last] line left)
                    last &= len(fileinfos[ifile][ipath].partitions) == 1
                return last

            def remove_one_of_the_first_partitions():
                maxdelta, ibestfile = None, None
                for ifile in range(len(fileinfos)):
                    if len(fileinfos[ifile][ipath].partitions) == 1:  # if this is the last line (i.e. there aren't any more glomeration steps in this file), leave it alone
                        continue
                    thisdelta = fileinfos[ifile][ipath].logprobs[1] - fileinfos[ifile][ipath].logprobs[0]  # logprob difference between the next partition and this one
                    if maxdelta is None or thisdelta > maxdelta:
                        maxdelta = thisdelta
                        ibestfile = ifile
                # print '    ibest %d with %f - %f = %f' % (ibestfile, fileinfos[ibestfile][ipath].logprobs[1], fileinfos[ibestfile][ipath].logprobs[0], fileinfos[ibestfile][ipath].logprobs[1] - fileinfos[ibestfile][ipath].logprobs[0])
                fileinfos[ibestfile][ipath].remove_first_partition()

            def add_next_global_partition():
                global_partition = []
                global_logprob = 0.
                for ifile in range(len(fileinfos)):  # combine the first line in each file to make a global partition
                    for cluster in fileinfos[ifile][ipath].partitions[0]:
                        global_partition.append(list(cluster))
                    global_logprob += fileinfos[ifile][ipath].logprobs[0]
                global_adj_mi = -1
                if calc_adj_mi:
                    global_adj_mi = utils.mutual_information(global_partition, self.reco_info, debug=False) if self.reco_info is not None else -1
                self.paths[ipath].add_partition(global_partition, global_logprob, n_procs=len(fileinfos), logweight=0., adj_mi=global_adj_mi)  # don't know the logweight yet (or maybe at all!)

            while not last_one():
                add_next_global_partition()
                remove_one_of_the_first_partitions()
            add_next_global_partition()


            if smc_particles > 1:
                self.paths[ipath].set_synthetic_logweight_history(self.reco_info)
            if debug:
                print '  merged path:'
                self.paths[ipath].print_partitions(self.reco_info, one_line=True)
            else:
                print '  merged path %d with %d glomeration steps and %d final clusters' % (ipath, len(self.paths[ipath].partitions), len(self.paths[ipath].partitions[-1]))

        if smc_particles == 1:  # XX: ...whereas if we're *not* doing smc, we have to add the previous histories *afterward*, since the previous histories are all in one piece
            if previous_info is None:
                if debug:
                    print '  no previous history'
            else:
                # TODO prevent this from adding duplicate adjacent partitions
                if debug:
                    print 'prepend previous history'
                if debug:
                    print '    before'
                    assert len(self.paths) == 1  # in case gremlins sneak in and add some between lines of code
                    self.paths[0].print_partitions(self.reco_info, one_line=True)
                # initial_path_index = fileinfos[ifile][ipath].initial_path_index  # which previous path are we hooking up to?
                previous_path = previous_info
                current_path = self.paths[0]
                # first_new_logprob = UPDATEME current_path.logprobs[0]
                extended_path = ClusterPath(None)
                for ip in range(len(previous_path.partitions)):
                    # if previous_path.logprobs[ip] >= first_new_logprob:  # skip the merges past which we rewound
                    #     continue
                    extended_path.add_partition(list(previous_path.partitions[ip]), previous_path.logprobs[ip], previous_path.n_procs[ip], logweight=previous_path.logweights[ip], adj_mi=previous_path.adj_mis[ip])
                for ip in range(len(current_path.partitions)):
                    extended_path.add_partition(list(current_path.partitions[ip]), current_path.logprobs[ip], current_path.n_procs[ip], logweight=current_path.logweights[ip], adj_mi=current_path.adj_mis[ip])
                self.paths[0] = extended_path
                # self.paths[0].set_synthetic_logweight_history(self.reco_info)  # need to multiply the combinatorical factors in the later partitions by the factors from the earlier partitions
                if debug:
                    print '    after'
                    self.paths[0].print_partitions(self.reco_info, one_line=True)

    # ----------------------------------------------------------------------------------------
    def read_cached_agglomeration(self, infnames, smc_particles, previous_info=None, calc_adj_mi=False, debug=False):
        """ Read the partitions output by bcrham. If <all_partitions> is specified, add the info to it """
        start = time.time()
        fileinfos = []
        for fname in infnames:
            fileinfos.append(self.read_file_info(fname, smc_particles, calc_adj_mi))
        self.merge_fileinfos(fileinfos, smc_particles, calc_adj_mi, previous_info=previous_info, debug=debug)
        print '        read cached glomeration time: %.3f' % (time.time()-start)

        return self.paths
