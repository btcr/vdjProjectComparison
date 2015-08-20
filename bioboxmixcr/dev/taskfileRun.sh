#!/bin/bash
#This script runs the biobox for mixcr. It is referenced as the entrypoint in the Dockerfile.
echo '#=============================================='
echo 'CHECK(exit scripts if cases fail)'
# exit script if one command fails
set -o errexit
# exit script if Variable is not set
set -o nounset
echo '#=============================================='
echo 'ASSIGNING BASIC VARIABLES'
YAMLINPUT=/bbx/input/biobox.yml
DOCKEROUTPUTDIR=/bbx/output
TASK=$1
mkdir -p ${DOCKEROUTPUTDIR}
echo '#=============================================='
echo 'CACHING PARAMETERS'
. ./inputDir/parse_yaml.sh
eval $(parse_yaml $YAMLINPUT 'mixcr_')
echo $YAMLINPUT

INPUTFILE=$mixcr_inputfile
#if the input file is in csv or tsv format run conversion scripts into fasta
if [ ${INPUTFILE: -4} == ".csv" ] ; then
	#run csv conversion script
	echo '  RUNNING CSV CONVERSION'
	python python/csv2fasta.py $INPUTFILE
	INPUTFILE=${INPUTFILE:0:${#INPUTFILE}-4}'.fasta'
elif [ ${INPUTFILE: -4} == ".tsv" ] ; then 
	#run tsv conversion script
	echo '	RUNNING TSV CONVERSION'
	python python/tsv2fasta.py $INPUTFILE
	INPUTFILE=${INPUTFILE:0:${#INPUTFILE}-4}'.fasta'
fi
echo '#=============================================='
echo 'GENERATING TASKFILE'
CURRENTDIR=$(pwd)
echo $CURRENTDIR
echo $INPUTFILE
echo -n 'default: export PATH=${CURRENTDIR}:$PATH && mixcr align ${INPUTFILE} output_file.vdjca && ' >> ./Taskfile
echo -n 'mixcr exportAlignments' >> ./Taskfile
#INSERT COMMAND LINE PARAMETERS HERE
echo -n ' output_file.vdjca /bbx/output/output.txt' >> ./Taskfile
ls
cat Taskfile
echo '#=============================================='
echo 'PROCESSING COMMAND'
CMD=$(egrep ^${TASK}: ./Taskfile | cut -f 2 -d ':')
if [[ -z ${CMD} ]]; then
	echo "Abort, no task found for '${TASK}'."
	exit 1
fi
echo $CMD
eval $CMD
echo 'PROCESS COMPLETED'



