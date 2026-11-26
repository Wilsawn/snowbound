#!/bin/zsh
# Shows the whole-route sweep's progress every 30 s: chunks done, elapsed time, time left (estimated from the pace so far).
# Run: ~/snowbound/scripts/sweep_timer.sh   (Ctrl+C to stop watching; the sweep keeps running)
DIR=~/snowbound/results/chunks/route-chunks; TOTAL=23; START=$(date +%s); D0=$(ls $DIR 2>/dev/null | grep -c done)
while true; do
  D=$(ls $DIR 2>/dev/null | grep -c done); NOW=$(date +%s); EL=$((NOW-START)); NEW=$((D-D0))
  if [ $NEW -gt 0 ]; then LEFT=$(( (TOTAL-D) * EL / NEW )); LEFTS=$(printf "%dh %02dm" $((LEFT/3600)) $((LEFT%3600/60))); else LEFTS="estimating (first chunk takes about 50 min)"; fi
  printf "\r%s  done %2d/%d  running %dh %02dm  left %s   " "$(date +%H:%M)" $D $TOTAL $((EL/3600)) $((EL%3600/60)) "$LEFTS"
  [ $D -ge $TOTAL ] && { echo; echo "SWEEP DONE"; break; }
  sleep 30
done
