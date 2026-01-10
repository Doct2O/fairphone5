#!/system/bin/sh
# set -x

if [ "$(id -u)" -eq 0 ] ; then
  echo "Please do not run as a root."
  exit
fi

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
ROUTER_ROUTER_RUN_CMD="python ${SCRIPT_DIR}/diag-router-router.py"
PTY_LINK_NAME="${SCRIPT_DIR}/ttyDiag"

echo "[*] Closing diag backend."
if ! ${ROUTER_ROUTER_RUN_CMD} --cmd close > /dev/null ; then
    echo "[-] Failed to close diag backend."
    exit 1
fi

rm -f "${PTY_LINK_NAME}"
echo "[+] Diag backend closed. Status:"
if ! ${ROUTER_ROUTER_RUN_CMD} --cmd status 2>/dev/null ; then
	echo "-= FAILED TO GET STATUS =-"
fi