#!/bin/bash

# Safety Stream Event Emitter
# Usage: ./emit.sh --type layer_start --layer 1 --name "Safety Check"

emit_event() {
    local type=$1
    local layer=$2
    local message=$3
    local data=$4

    local json="{\"type\":\"$type\""

    if [ ! -z "$layer" ] && [ "$layer" != "null" ]; then
        json="$json,\"layer\":$layer"
    fi

    if [ ! -z "$message" ]; then
        json="$json,\"message\":\"$message\""
    fi

    if [ ! -z "$data" ]; then
        json="$json,\"data\":$data"
    fi

    json="$json}"

    curl -s -X POST http://localhost:9999/emit \
        -H "Content-Type: application/json" \
        -d "$json" > /dev/null 2>&1
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --type) TYPE="$2"; shift 2 ;;
        --layer) LAYER="$2"; shift 2 ;;
        --name) NAME="$2"; shift 2 ;;
        --message) MESSAGE="$2"; shift 2 ;;
        --decision) DECISION="$2"; shift 2 ;;
        --time) TIME="$2"; shift 2 ;;
        --data) DATA="$2"; shift 2 ;;
        *) shift ;;
    esac
done

case "$TYPE" in
    "input")
        emit_event "input_received" "null" "$MESSAGE" ""
        ;;
    "layer_start")
        emit_event "layer_start" "$LAYER" "" "{\"name\":\"$NAME\"}"
        ;;
    "layer_progress")
        emit_event "layer_progress" "$LAYER" "" "{\"percent\":$MESSAGE}"
        ;;
    "layer_complete")
        DATA="{\"decision\":\"$DECISION\""
        if [ ! -z "$TIME" ]; then
            DATA="$DATA,\"execution_time_ms\":$TIME"
        fi
        DATA="$DATA}"
        emit_event "layer_complete" "$LAYER" "" "$DATA"
        ;;
    "output")
        emit_event "output_ready" "null" "$MESSAGE" ""
        ;;
    *)
        echo "Unknown event type: $TYPE"
        exit 1
        ;;
esac
