#!/system/bin/sh

if [ "$(id -u)" -ne 0 ]; then
  echo "Please run as a root."
  exit
fi

printf "\033[2J"
while true; do
  printf "\033[H"
  echo "=== Fairphone 5 Live Temperatures ==="
  for z in /sys/class/thermal/thermal_zone*; do
    t=$(cat "$z/type" 2>/dev/null)
    v=$(cat "$z/temp" 2>/dev/null)
    case "$t" in *cpu*|*gpu*|bat*|*skin*)
      printf "%-20s : %d°C      \n" "$t" $((v/1000))
      ;;  
    esac
  done
  sleep 2
done
