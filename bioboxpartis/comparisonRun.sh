#This file contains commands to run the biobox encased Partis project
python input_data/YamlFileGenerator.py
mv biobox.yml ./input_data
docker build -t bioboxpartis ./bioboxpartis 
docker run --volume="$(pwd)/input_data:/bbx/input:ro" --volume="$(pwd)/output_data:/bbx/output:rw" bioboxpartis default
