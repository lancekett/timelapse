#!/bin/bash

function help() {
  echo "Capture photos"
  echo
  echo "Options:"
  echo "-h    Show this help info and quit"
  echo "-u    Photo URL (required)"
  echo "-d    Seconds to delay between captures (default: 5)"
  echo
  echo "Usage:"
  echo "$0 -h"
  echo "$0 -u http://192.168.42.64/photo -d 1"
  echo
  echo "Press ctrl+c to quit"
}

url=
delay=5
sunset_hhmm=$(hdate -s -z -8 -l N46.5 -L W123 | grep sunset | awk '{print $2}')
sunrise_hhmm=$(hdate -s -z -8 -l N46.5 -L W123 | grep sunrise | awk '{print $2}')
sunrise=$(date -d $sunrise_hhmm +%s)
sunset=$(date -d $sunset_hhmm +%s)

while getopts "h?u:d:" opt; do
  case "$opt" in
    h) help; exit ;;
    u) url="$OPTARG" ;;
    d) delay="$OPTARG" ;;
    *) help; exit ;;
  esac
done

if [[ -z "$url" ]]; then
  echo 'No URL found'
  exit 1
fi

dir=$(dirname "$0")

while true; do
  sunrise=$(date -d $sunrise_hhmm +%s)
  sunset=$(date -d $sunset_hhmm +%s)
  hourago=$(date -d '-1 hour' +%s)
  hourfuture=$(date -d '+1 hour' +%s)

  day=$(date +%F)
  timestamp="$(date +%s)"

  mkdir -p capture-$day
  mkdir -p output-$day

  if [ $hourfuture -gt $sunrise ] && [ $hourago -lt $sunset ]
  then
    curl -L "$url" > "$dir/capture-$day/$timestamp.jpg"
  else
    echo "sleeping..."
    # if $($hourfuture < "24:00") #?? not sure if this works.
    # then
    #   touch $dir/capture-$day/done
    # fi
  fi
  sleep "$delay"

done
