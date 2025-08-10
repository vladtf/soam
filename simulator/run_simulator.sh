#!/bin/sh
set -e

# Check if the SIMULATOR_TYPE environment variable is set
if [ -z "$SIMULATOR_TYPE" ]; then
  echo "Error: SIMULATOR_TYPE environment variable is not set."
  echo "Please set it to one of: temperature, traffic, air_quality, smart_bin"
  exit 1
fi

# Run the appropriate simulator based on the environment variable
case "$SIMULATOR_TYPE" in
  temperature)
    echo "Starting temperature simulator..."
    exec python -m simulators.temperature_simulator
    ;;
  traffic)
    echo "Starting traffic simulator..."
    exec python -m simulators.traffic_simulator
    ;;
  air_quality)
    echo "Starting air quality simulator..."
    exec python -m simulators.air_quality_simulator
    ;;
  smart_bin)
    echo "Starting smart bin simulator..."
    exec python -m simulators.smart_bin_simulator
    ;;
  *)
    echo "Error: Unknown SIMULATOR_TYPE '$SIMULATOR_TYPE'"
    echo "Valid options are: temperature, traffic, air_quality, smart_bin"
    exit 1
    ;;
esac
