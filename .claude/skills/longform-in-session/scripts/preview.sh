#!/usr/bin/env bash
# 앱 전송 한도(30MB) 안에 들어가는 전체 길이 미리보기(480p, 2-pass)를 만든다.
# 원본 1080p 10분은 200MB 이상이라 SendUserFile로 보낼 수 없다(30MB 초과 거부, 큰 파일은 502).
# 사용: preview.sh <final.mp4> <out.mp4>
set -euo pipefail
IN=$(realpath "$1"); OUT=$(realpath -m "$2")
DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$IN")
# 28MB 목표: 총 비트레이트(kbps) = 28*8*1024/DUR, 오디오 64k 제외
VB=$(python3 -c "print(max(150, int(28*8*1024/$DUR - 64)))")
TMP=$(mktemp -d)
( cd "$TMP" && ffmpeg -v error -y -i "$IN" -vf scale=854:480 -c:v libx264 -preset slow -b:v ${VB}k -pass 1 -an -f mp4 /dev/null \
  && ffmpeg -v error -y -i "$IN" -vf scale=854:480 -c:v libx264 -preset slow -b:v ${VB}k -pass 2 -c:a aac -b:a 64k -movflags +faststart "$OUT" )
rm -rf "$TMP"
ls -la "$OUT"
