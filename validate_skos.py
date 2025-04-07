#!/usr/bin/env python3
import argparse
import sys
import os
import zipfile
import tempfile
from rdflib import Graph, Namespace
from rdflib.namespace import RDF

def validate_skos(graph: Graph) -> bool:
    # Define the SKOS namespace
    SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")
    
    # Check for at least one skos:Concept defined by rdf:type
    concepts = list(graph.subjects(predicate=RDF.type, object=SKOS.Concept))
    # If not found, check for any resource with a skos:prefLabel
    if not concepts:
        concepts = list(graph.subjects(predicate=SKOS.prefLabel))
    return bool(concepts)

def process_file(file_path: str, rdf_format: str) -> bool:
    graph = Graph()
    try:
        graph.parse(file_path, format=rdf_format)
    except Exception as e:
        print(f"Error parsing RDF file '{file_path}': {e}")
        return False
    if validate_skos(graph):
        print(f"'{file_path}': Valid SKOS file: True.")
        return True
    else:
        print(f"'{file_path}': Valid SKOS file: False.")
        return False

def main():
    parser = argparse.ArgumentParser(
        description='Validate if an RDF file or a ZIP archive of RDF files has proper SKOS format.'
    )
    parser.add_argument('input', help='Path to an RDF file or a ZIP file containing RDF files.')
    parser.add_argument('--format', default=None,
                        help='RDF format of the file (e.g., xml, ttl, nt, json-ld). '
                             'If omitted, rdflib will try to guess the format.')
    args = parser.parse_args()

    input_path = args.input
    rdf_format = args.format

    # Check if the input is a ZIP archive
    if zipfile.is_zipfile(input_path):
        with tempfile.TemporaryDirectory() as tmpdirname:
            with zipfile.ZipFile(input_path, 'r') as zip_ref:
                zip_ref.extractall(tmpdirname)
            valid_count = 0
            total_count = 0
            # Recursively process files in the extracted folder
            for root, _, files in os.walk(tmpdirname):
                for file in files:
                    file_path = os.path.join(root, file)
                    total_count += 1
                    if process_file(file_path, rdf_format):
                        valid_count += 1
            print(f"\nProcessed {total_count} files; {valid_count} valid SKOS files.")
            if valid_count == total_count:
                sys.exit(0)
            else:
                sys.exit(1)
    else:
        # Process a single file
        if process_file(input_path, rdf_format):
            sys.exit(0)
        else:
            sys.exit(1)

if __name__ == '__main__':
    main()
