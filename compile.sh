#!/bin/bash

function help() {
  echo "Assemble captured photos into timelapse"
  echo
  echo "Options:"
  echo "-h    Show this help info and quit"
  echo "-s    Filename slug (default: day)"
  echo "-r    Frame rate (default: 30)"
  echo "-y    Day to use for compiling in a directory"
  echo "-d    Prompt to delete capture files when done (default: false)"
  echo "-f    final run for the day."
  echo
  echo "Usage:"
  echo "$0 -h"
  echo "$0 -s FILENAME_SLUG -r 30"
}

day=$(date +%F)
hhmm=$(date +%H%M)
framerate=30
delete=false
final=false

while getopts "h?s:r:y:d:f" opt; do
  case "$opt" in
    h) help; exit ;;
    s) slug="$OPTARG" ;;
    r) framerate="$OPTARG" ;;
    y) day="$OPTARG" ;;
    d) delete=true ;;
    f) final=true ;;
    *) help; exit ;;
  esac
done

slug="$day"
dir=$(dirname "$0")

mkdir -p output-$day

if $final; then
  filename="$dir/output-$day/$slug-$framerate.mp4"
  find "capture-$day/" -type f -size 0 -delete
else
  filename="$dir/output-$day/$slug-$framerate-$hhmm.mp4"
fi

function video() {
  ffmpeg \
    -r "$framerate" \
    -pattern_type glob -i "$dir/capture-$day/*.jpg" \
    -movflags faststart \
    -s:v 1440x1080 \
    -c:v libx264 \
    -crf 23 \
    -pix_fmt yuv420p \
    "$filename"
}

function cleanup() {
  count=$(find "capture-$day/*.jpg" | wc -l | xargs)

  echo
  read -p "All done! Delete $count captured photos? [Y/n] " -n 1 -r
  echo

  if [[ $REPLY =~ ^[Y]$ ]]; then
    echo "rm capture-$day/*"
  else
    exit
  fi
}

video

if $delete; then
  cleanup
fi
