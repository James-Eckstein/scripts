#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
#  Fire Stick -> Projectivy Launcher, all-in-one (run in Termux)
#  Finds the Fire Stick on your Wi-Fi, installs Projectivy,
#  and switches on the permission it needs.
#  Optional: FIRE_IP=192.168.x.x bash fire-projectivy.sh
# ============================================================
main() {
G='\033[1;32m'; R='\033[1;31m'; Y='\033[1;33m'; N='\033[0m'
say(){ echo -e "${G}▶ $*${N}"; }
warn(){ echo -e "${Y}⚠ $*${N}"; }
die(){ echo -e "${R}✖ $*${N}"; exit 1; }

say "Installing tools (can take a minute)..."
yes | pkg update >/dev/null 2>&1
pkg install -y android-tools apkeep unzip net-tools >/dev/null 2>&1 \
  || die "Couldn't install tools - check your internet and try again."

# ---- Find the Fire Stick ------------------------------------
FIRE="${FIRE_IP:-}"
try_ip() {
  local ip="$1"
  adb connect "$ip:5555" >/dev/null 2>&1; sleep 1
  if adb devices | grep "$ip:5555" | grep -q unauthorized; then
    warn "Look at the TV: tick 'Always allow from this computer', then press OK"
    for _ in $(seq 1 45); do
      sleep 2; adb devices | grep "$ip:5555" | grep -q 'device$' && break
    done
  fi
  [ "$(adb -s "$ip:5555" shell getprop ro.product.manufacturer 2>/dev/null | tr -d '\r')" = "Amazon" ]
}

if [ -n "$FIRE" ]; then
  try_ip "$FIRE" || die "Couldn't reach a Fire Stick at $FIRE"
else
  say "Looking for your Fire Stick on the Wi-Fi..."
  SUBNETS=$(ifconfig 2>/dev/null | grep -oE 'inet (192\.168\.|10\.|172\.)[0-9.]+' \
            | awk '{print $2}' | cut -d. -f1-3 | sort -u)
  [ -z "$SUBNETS" ] && SUBNETS="192.168.0 192.168.1 192.168.68 10.0.0"
  for S in $SUBNETS; do
    for ip in $(for i in $(seq 1 254); do
                  (timeout 0.4 bash -c "</dev/tcp/$S.$i/5555" 2>/dev/null && echo "$S.$i") &
                done; wait); do
      try_ip "$ip" && { FIRE="$ip"; break 2; }
    done
  done
fi
[ -z "$FIRE" ] && die "No Fire Stick found.
  On the Fire Stick: Settings > My Fire TV > Developer Options > ADB Debugging = ON
  (no Developer Options? Settings > My Fire TV > About > click the name 7 times)
  and make sure this phone is on the same Wi-Fi."
say "Found Fire Stick at $FIRE"
A="adb -s $FIRE:5555"

# ---- Download + install Projectivy --------------------------
ABI=$($A shell getprop ro.product.cpu.abi | tr -d '\r')
D="$TMPDIR/projectivy"; rm -rf "$D"; mkdir -p "$D"
say "Downloading Projectivy Launcher ($ABI)..."
apkeep -a com.spocky.projengmenu -d apk-pure -o "arch=$ABI" "$D" >/dev/null 2>&1 \
  || { rm -rf "$D"; die "Download failed - try again in a bit."; }
F=$(ls "$D"/* | head -1)
say "Installing on the TV..."
case "$F" in
  *.xapk) unzip -o -q "$F" -d "$D/x" && $A install-multiple -r $(find "$D/x" -name '*.apk') ;;
  *)      $A install -r "$F" ;;
esac >/dev/null || { rm -rf "$D"; die "Install failed."; }
rm -rf "$D"

# ---- Switch on the accessibility permission -----------------
SVC=$($A shell dumpsys package com.spocky.projengmenu | tr -d '\r' \
      | grep -o 'com.spocky.projengmenu/[A-Za-z0-9._]*' | grep -i access | head -1)
if [ -n "$SVC" ]; then
  CUR=$($A shell settings get secure enabled_accessibility_services | tr -d '\r')
  if [ -z "$CUR" ] || [ "$CUR" = "null" ]; then NEW="$SVC"
  elif echo "$CUR" | grep -q "$SVC"; then NEW="$CUR"
  else NEW="$CUR:$SVC"; fi
  $A shell settings put secure enabled_accessibility_services "$NEW"
  $A shell settings put secure accessibility_enabled 1
else
  warn "Couldn't switch on the permission automatically - Projectivy will ask for it."
fi

$A shell monkey -p com.spocky.projengmenu 1 >/dev/null 2>&1
echo
say "All done! Projectivy is open on the TV."
echo -e "${Y}Last step on the TV:${N} gear icon > Projectivy Launcher settings > General > turn ON 'Override current launcher'"
}
main "$@" </dev/null
