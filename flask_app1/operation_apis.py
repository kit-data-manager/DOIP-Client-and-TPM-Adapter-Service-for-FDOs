from flask import Flask, request, jsonify
import re
import requests
from jsonschema import validate
from jsonschema.exceptions import ValidationError
import os
import tarfile
import zstandard as zstd
from flask import Flask, request, send_file
from PIL import Image
from io import BytesIO
import io
import zipfile
import numpy as np
import tempfile
import shutil
import json
from urllib.parse import urlparse

app = Flask(__name__)

# Updated regex patterns for a broader range of license types
license_patterns = {
    "open_access": [
        # Creative Commons Licenses
        re.compile(r"creativecommons\.org\/licenses\/(by|by-sa)\/", re.IGNORECASE),
        re.compile(r"creativecommons\.org\/publicdomain\/zero\/1\.0\/", re.IGNORECASE),  # CC0
        # Open Source Software Licenses
        re.compile(r"opensource\.org\/licenses\/(Apache-2\.0|MIT|GPL-2\.0|GPL-3\.0|LGPL-2\.1|LGPL-3\.0|BSD-2-Clause|BSD-3-Clause|EPL-1\.0|EPL-2\.0|Mozilla-2\.0)", re.IGNORECASE),
        re.compile(r"gnu\.org\/licenses\/(gpl|agpl|lgpl)-", re.IGNORECASE),
        re.compile(r"spdx\.org\/licenses\/(Apache-2\.0|MIT|GPL-2\.0-only|GPL-2\.0-or-later|GPL-3\.0-only|GPL-3\.0-or-later|LGPL-2\.1-only|LGPL-2\.1-or-later|LGPL-3\.0-only|LGPL-3\.0-or-later|BSD-2-Clause|BSD-3-Clause)", re.IGNORECASE),
        # Specific to academic and open data
        re.compile(r"opendatacommons\.org\/licenses\/(pddl|odbl|by)\/", re.IGNORECASE),  # Open Data Commons
    ],
    "non_open_access": [
        # Creative Commons Non-Commercial or No-Derivatives
        re.compile(r"creativecommons\.org\/licenses\/(by-nd|by-nc|by-nc-sa|by-nc-nd)\/", re.IGNORECASE),
        # Typical proprietary licenses - no standard URL patterns, example patterns below
        re.compile(r"terms|eula|license|end-user-agreement", re.IGNORECASE),  # General catch-all for various proprietary license agreements
        # Example patterns for known proprietary software
        re.compile(r"microsoft\.com\/software-license-terms", re.IGNORECASE),
        re.compile(r"adobe\.com\/products\/eulas", re.IGNORECASE),
        # Some proprietary content licenses
        re.compile(r"gettyimages\.com\/eula", re.IGNORECASE),
        # Academic journals and publisher-specific licenses not classified as open access
        re.compile(r"elsevier\.com\/userlicense\/1\.0\/", re.IGNORECASE),
        re.compile(r"springer\.com\/terms\/of+use", re.IGNORECASE),
        # Paywalled content
        re.compile(r"paywall", re.IGNORECASE),
    ]
}


def evaluate_license(license_type, license_url):
    """
    Evaluates if the license URL matches the requested license type (open access or not).
    Uses predefined URL patterns to determine the license type.
    """
    is_open_access_requested = re.search(r"open(\s|-)?(access|ly)?", license_type, re.IGNORECASE)

    
    # Check against open access patterns
    for pattern in license_patterns["open_access"]:
        if pattern.search(license_url):
            return is_open_access_requested  # True if open access is requested and URL is open access
    
    # Check against non-open access patterns
    for pattern in license_patterns["non_open_access"]:
        if pattern.search(license_url):
            return not is_open_access_requested  # True if open access is not requested and URL is not open access
    
    return False  # If no patterns match, return False

@app.route('/evaluate_license', methods=['POST'])
def evaluate_license_api():
    license_type = request.args.get('licenseType')
    license_url = request.json.get('licenseURL')
    if not license_type or not license_url:
        return jsonify({"error": "Missing licenseType or licenseURL"}), 400
    
    match = evaluate_license(license_type, license_url)
    
    # Convert the match result into a serializable form
    result = bool(match)  # Example: Converts to True if match is found, False otherwise
    
    return jsonify({"result": result})

def validate_orcid(orcid):
    orcid_url_pattern = r"https?://orcid\.org/(\d{4}-\d{4}-\d{4}-\d{3}[0-9X])"
    orcid_pattern = r"\d{4}-\d{4}-\d{4}-\d{3}[0-9X]"
    match_url = re.search(orcid_url_pattern, orcid)
    match_orcid = re.search(orcid_pattern, orcid)
    if match_url:
        orcid_id = match_url.group(1)
        url = f"https://pub.orcid.org/v3.0/{orcid_id}/person"
        return url
    elif match_orcid:
        orcid_id = orcid
        url = f"https://pub.orcid.org/v3.0/{orcid_id}/person"
        return url
    else:
        return "400"

@app.route('/get_orcid', methods=['GET'])
def get_orcid():
    # Extract the ORCID ID from the request body
    try:
        orcid_input = request.args.getlist('orcid')
    except Exception:
        orcid_input = request.args.get('orcid')
    headers = {
        'Accept': 'application/json',
    }
    if not orcid_input:
        return jsonify({"error": "Missing ORCID ID"}), 400
    elif isinstance(orcid_input, list):
        orcid_profiles = []
        for orcid in orcid_input:
            url = validate_orcid(orcid)
            if url != "400":
                response = requests.get(url, headers=headers)
                # Check if the request was successful
                if response.status_code == 200:
                    # Return the ORCID profile information
                    orcid_profiles.append(response.json())
                else:
                   pass                
            else:
                return jsonify({"error": "No valid ORCiD"}), 400
        if len(orcid_profiles) > 0:
            return jsonify(orcid_profiles)
        else:
            return jsonify({"error": "No valid ORCiDs"}), 400
    else:
        url = validate_orcid(orcid)
        if url != "400":
            response = requests.get(url, headers=headers)
            # Check if the request was successful
            if response.status_code == 200:
                # Return the ORCID profile information
                return jsonify(response.json())
            else:
                # Return an error message if something went wrong
                return jsonify({"error": "Failed to retrieve ORCID profile"}), response.status_code
        else:
            return jsonify({"error": "No valid ORCiD"}), 400

    # Define the URL for the ORCID API request
    # The URL structure is: https://pub.orcid.org/v3.0/{ORCID_ID}/person
    
    
    # Set the Accept header to receive JSON response
    

    # Make the request to the ORCID API
    response = requests.get(url, headers=headers)
    
    

def fetch_records(pids):
    records = []
    # using the local json files for TPM mocking in testing environment. 
    # In production environement, a running TPM instance configured with the Handle Registry is used.
    script_dir = os.path.dirname(__file__)  # Directory of the script
    data_dir = os.path.join(script_dir, 'original_records')  # Path to the "data" directory
    for filename in os.listdir(data_dir):
        if filename.endswith('.json'):  # Check if the file is a JSON file
            filepath = os.path.join(data_dir, filename)  # Full path to the file
            
            # Open and read the JSON file
            with open(filepath, 'r', encoding='utf-8') as json_file:
                record = json.load(json_file)  # Load file content into a Python dictionary
                if record["pid"] in pids:
                    records.append(record)
    return records

@app.route('/find_metadata', methods=['GET'])
def find_metadata():
    pids = request.args.get('pids')
    
    if not pids:
        return jsonify({"error": "No PIDs provided"}), 400

    records = fetch_records(pids)
    return jsonify(records)

@app.route('/find_annotation', methods=['GET'])
def find_annotation():
    pids = request.args.get('pids')
    if not pids:
        return jsonify({"error": "No PIDs provided"}), 400

    records = fetch_records(pids)
    return jsonify(records)

@app.route('/find_software', methods=['GET'])
def find_software():
    pids = request.args.get('pids')
    if not pids:
        return jsonify({"error": "No PIDs provided"}), 400

    records = fetch_records(pids)
    return jsonify(records)

@app.route('/find_literature', methods=['GET'])
def find_literature():
    pids = request.args.get('pids')
    if not pids:
        return jsonify({"error": "No PIDs provided"}), 400

    records = fetch_records(pids)
    return jsonify(records)

@app.route('/validate_schema', methods=['GET'])
def validate_schema():
    metadata_url = request.args.get('metadata')
    schema_url = request.args.get('schema')
    
    if not metadata_url or not schema_url:
        return jsonify({"error": "Both metadataUrl and schemaUrl are required"}), 400

    try:
        # Fetch the schema
        schema_response = requests.get(schema_url)
        schema_response.raise_for_status()  # Raises a HTTPError if the response is not 2xx
        schema = schema_response.json()
        
        # Fetch the metadata document
        metadata_response = requests.get(metadata_url)
        metadata_response.raise_for_status()
        document = metadata_response.json()
        
        # Validate the document against the schema
        validate(instance=document, schema=schema)
        return jsonify({"isValid": True})
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Failed to fetch documents: {str(e)}"}), 500
    except ValidationError as e:
        return jsonify({"isValid": False, "message": str(e)}), 400

@app.route('/get_thumbnail', methods=['GET'])
def get_thumbnail():
    # Extract the URL from the request data
    url = request.args.get('url')
    checksum = request.args.get('checksum')
    supported_domains = ["zenodo.org"]
    # internal database. Would be typically a relational database, specific to a repository like Zenodo. Here, it uses the checksums of files to identify their corresponding image finger print.
    internal_database = {"716acce83a51ad2fc958ab3ce0026f71": "716acce83a51ad2fc958ab3ce0026f71.png",
        "57219d1c2d8917a85c1ea32459f61a84": "57219d1c2d8917a85c1ea32459f61a84.png",
        "9df9c0b8e48a98f2ae4efa19ec62d996": "9df9c0b8e48a98f2ae4efa19ec62d996.png",
        "8aca44b36e15e61478debffdb9edda18": "8aca44b36e15e61478debffdb9edda18.png",
        "850f11548064ae5c8ef7e376de54e7cf": "850f11548064ae5c8ef7e376de54e7cf.png",
        "aa1fb7275480142c04070859b8a2b5a5": "aa1fb7275480142c04070859b8a2b5a5.png"}
    if not url:
        return jsonify({"error": "URL is required"}), 400
    
    pattern = '|'.join(re.escape(domain) for domain in supported_domains)
    # Check if the checksum is in the internal database
    if re.search(pattern, url):
        pass
    else:
        return jsonify({"error": "Domain not trusted"}), 403

    try:
        checksum = json.loads(checksum)
    
    except json.JSONDecodeError as e:
        pass
    if isinstance(checksum, dict):
        if "md5sum" in checksum:
            checksum = checksum["md5sum"]
        elif "sha256sum" in checksum:
            checksum = checksum["sha256sum"]
        elif "sha160sum" in checksum:
            checksum = checksum["sha160sum"]
        elif "sha512sum" in checksum:
            checksum = checksum["sha512sum"]
        elif "sha224sum" in checksum:
            checksum = checksum["sha224sum"]
        elif "sha384sum" in checksum:
            checksum = checksum["sha384sum"]
    if str(checksum) in internal_database:
        pass
    else:
        return jsonify({"error": "Checksum not known"}), 403

    image_file_path = os.path.join(os.path.dirname(__file__), 'image_files', internal_database[checksum])
    
    if os.path.exists(image_file_path):
        # Serve the png file to the client
        return send_file(image_file_path, as_attachment=True, mimetype='image/png')
    else:
        return jsonify({"error": "PNG file not found"}), 404
    

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
