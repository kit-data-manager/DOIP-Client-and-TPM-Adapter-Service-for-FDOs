#!/usr/bin/env bash

HOSTURL="http://localhost:8090/api/v1/pit/pid/?dryrun=false"

help()
{
   # Display Help
   echo "This script is to create FAIR DOs."
   echo
   echo "Syntax: scriptTemplate"
   echo "options:"
   echo "-h|--help     Print this Help."
   echo "-v|--verbose  Verbose Output"
   echo "--put        execute put request"
   echo "--post       execute post request"
   echo "--id         specify id (only on put)"
   echo "--file       Specify a json file"
   echo "--dir        Specify directory containing JSON files"
   echo
}

while true; do
  case "$1" in
    -h | --help )
        help
        exit ;;
    -v | --verbose )
        VERBOSE=1
        shift ;;
    --put)
        PUT=1
        shift ;;
    --post)
        POST=1
        shift ;;
    --id)
        ID=$2
        shift 2 ;;
    --file)
        FILE=$2
        shift 2 ;;
    --dir)
        DIRECTORY=$2
        shift 2 ;;
    * ) break ;;
  esac
done

process_file() {
    local file=$1
    local response
    local new_pid

    if [ ${POST} ]; then
        if [ ${VERBOSE} ]; then
            echo "Executing POST on ${HOSTURL} with File: ${file}"
        fi
        response=$(curl --silent --request POST \
          --url ${HOSTURL} \
          --header 'Content-Type: application/json' \
          --data @${file})
        echo "Response: $response"  # Display the response
    fi

    if [ ${PUT} ]; then
        if [ ${VERBOSE} ]; then
            echo "Executing PUT on ${HOSTURL} with File: ${file} and ID: ${ID}"
        fi
        response=$(curl --silent --request PUT \
          --url ${HOSTURL}${ID} \
          --header 'Content-Type: application/json' \
          --data @${file})
        echo "Response: $response"  # Display the response
    fi

    # Extract pid from the response
    new_pid=$(echo "${response}" | jq -r '.pid')

    # Update the original JSON file with the new pid
    if [ ! -z "${new_pid}" ] && [ "${new_pid}" != "null" ]; then
        jq --arg pid "${new_pid}" '.pid = $pid' "${file}" > temp.json && mv temp.json "${file}"
    fi
}


if [ "${DIRECTORY}" ]; then
    for file in "${DIRECTORY}"/*; do
        if [ -f "$file" ]; then
            process_file "$file"
        fi
    done
else
    process_file "${FILE}"
fi

